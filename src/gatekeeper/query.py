"""Query plans: a small JSON language the planner writes and this module turns into SQL.

A plan never contains SQL. It is validated field by field, compiled to a parameterised query
over the data module's connection and the raw aggregates go through the small-cell rule.

plan = {
  "unit": "patient" | "encounter",
  "population": [filter, ...],
  "group_by": [{"by": "region" | "data_holder" | "sex"} | {"by": "age_band", "bands": [[lo, hi|null], ...]}],
  "measures": [{"name": str, "kind": "count" | "percent" | "mean", "where": [filter, ...],
                "of": [filter, ...] (percent denominator, default the population),
                "value": {"loinc": str, "pick": "latest" | "earliest"} | {"field": "age"} (mean only)}]
}
filter = {"kind": ..., "negate": bool, ...}, kinds and fields in FILTER_FIELDS.
"""
import re
from decimal import Decimal
from itertools import product

from gatekeeper import data, smallcell

SCALE = 1_000_000
CODE = re.compile(r"^[A-Za-z0-9.\-]{1,12}$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
OPS = {">": ">", ">=": ">=", "<": "<", "<=": "<=", "=": "="}

FILTER_FIELDS = {
    "age": {"min", "max"},
    "sex": {"value"},
    "region": {"values"},
    "data_holder": {"values"},
    "condition": {"icd10_prefixes", "onset_from", "onset_to"},
    "medication": {"atc_prefixes", "active_on", "start_from", "start_to"},
    "observation": {"loinc", "pick", "op", "threshold", "date_from", "date_to"},
    "encounter": {"types", "primary_icd10_prefixes", "start_from", "start_to", "data_holders"},
}
GROUPS = {"region", "data_holder", "sex", "age_band"}
KINDS = {"count", "percent", "mean"}


class InvalidPlan(ValueError):
    pass


def _need(cond, msg):
    if not cond:
        raise InvalidPlan(msg)


def check_codes(values, what):
    _need(isinstance(values, list) and values, f"{what} must be a non-empty list")
    for v in values:
        _need(isinstance(v, str) and CODE.match(v), f"bad code in {what}: {v!r}")


def _texts(values, what):
    _need(isinstance(values, list) and values and all(isinstance(v, str) for v in values),
          f"{what} must be a non-empty list of strings")


def _date(v, what):
    _need(v is None or (isinstance(v, str) and DATE.match(v)), f"{what} must be YYYY-MM-DD")


def _check_filter(f, unit):
    _need(isinstance(f, dict) and f.get("kind") in FILTER_FIELDS, f"unknown filter: {f!r}")
    kind = f["kind"]
    extra = set(f) - FILTER_FIELDS[kind] - {"kind", "negate"}
    _need(not extra, f"{kind} filter has unknown fields {sorted(extra)}")
    if kind == "age":
        for k in ("min", "max"):
            _need(f.get(k) is None or isinstance(f[k], int), f"age {k} must be an integer")
    elif kind == "sex":
        _need(f.get("value") in ("female", "male"), "sex must be female or male")
    elif kind in ("region", "data_holder"):
        _texts(f.get("values"), kind)
    elif kind == "condition":
        check_codes(f.get("icd10_prefixes"), "icd10_prefixes")
        _date(f.get("onset_from"), "onset_from")
        _date(f.get("onset_to"), "onset_to")
    elif kind == "medication":
        check_codes(f.get("atc_prefixes"), "atc_prefixes")
        for k in ("active_on", "start_from", "start_to"):
            _date(f.get(k), k)
    elif kind == "observation":
        _need(isinstance(f.get("loinc"), str) and CODE.match(f["loinc"]), "observation needs loinc")
        _need(f.get("pick", "latest") in ("latest", "earliest", "any"), "pick: latest, earliest or any")
        _need((f.get("op") is None) == (f.get("threshold") is None), "op and threshold go together")
        _need(f.get("op") is None or f["op"] in OPS, f"op must be one of {sorted(OPS)}")
        _need(f.get("threshold") is None or isinstance(f["threshold"], (int, float)), "threshold: number")
        _date(f.get("date_from"), "date_from")
        _date(f.get("date_to"), "date_to")
    elif kind == "encounter":
        if f.get("types") is not None:
            _texts(f["types"], "types")
        if f.get("primary_icd10_prefixes") is not None:
            check_codes(f["primary_icd10_prefixes"], "primary_icd10_prefixes")
        if f.get("data_holders") is not None:
            _texts(f["data_holders"], "data_holders")
        _date(f.get("start_from"), "start_from")
        _date(f.get("start_to"), "start_to")


def validate(plan):
    _need(isinstance(plan, dict), "plan must be an object")
    unit = plan.get("unit", "patient")
    _need(unit in ("patient", "encounter"), "unit must be patient or encounter")
    for f in plan.get("population", []):
        _check_filter(f, unit)
    for g in plan.get("group_by", []):
        _need(isinstance(g, dict) and g.get("by") in GROUPS, f"unknown group: {g!r}")
        if g["by"] == "age_band":
            bands = g.get("bands")
            _need(isinstance(bands, list) and bands, "age_band needs bands")
            for b in bands:
                _need(isinstance(b, list) and len(b) == 2 and isinstance(b[0], int)
                      and (b[1] is None or isinstance(b[1], int)), f"bad band {b!r}")
    measures = plan.get("measures")
    _need(isinstance(measures, list) and measures, "plan needs at least one measure")
    names = set()
    for m in measures:
        _need(isinstance(m, dict) and m.get("kind") in KINDS, f"bad measure {m!r}")
        _need(isinstance(m.get("name"), str) and m["name"] and m["name"] not in names,
              f"measure names must be unique strings: {m.get('name')!r}")
        names.add(m["name"])
        for f in m.get("where", []) + m.get("of", []):
            _check_filter(f, unit)
        if m["kind"] == "mean":
            v = m.get("value")
            _need(isinstance(v, dict) and (v.get("field") == "age" or (
                isinstance(v.get("loinc"), str) and CODE.match(v["loinc"])
                and v.get("pick", "latest") in ("latest", "earliest"))), "mean needs a value")
        _need(unit == "patient" or m["kind"] != "mean", "means are per patient")
    return plan


def like_any(col, prefixes, params):
    params.extend(f"{p}%" for p in prefixes)
    return "(" + " OR ".join(f"{col} LIKE ?" for _ in prefixes) + ")"


def _obs_value(loinc, pick, params):
    params.append(loinc)
    order = "DESC" if pick == "latest" else "ASC"
    return (f"(SELECT o.value FROM observations o WHERE o.patient_id = p.patient_id AND o.loinc = ? "
            f"ORDER BY o.date {order} LIMIT 1)")


def _filter_sql(f, unit, params):
    kind = f["kind"]
    if kind == "age":
        parts = []
        if f.get("min") is not None:
            parts.append("p.age >= ?")
            params.append(f["min"])
        if f.get("max") is not None:
            parts.append("p.age <= ?")
            params.append(f["max"])
        sql = " AND ".join(parts) or "1"
    elif kind == "sex":
        sql = "p.sex = ?"
        params.append(f["value"])
    elif kind in ("region", "data_holder"):
        col = "e.data_holder" if kind == "data_holder" and unit == "encounter" else f"p.{kind}"
        sql = f"{col} IN ({','.join('?' * len(f['values']))})"
        params.extend(f["values"])
    elif kind == "condition":
        cond = [like_any("c.icd10", f["icd10_prefixes"], params)]
        if f.get("onset_from"):
            cond.append("c.onset_date >= ?")
            params.append(f["onset_from"])
        if f.get("onset_to"):
            cond.append("c.onset_date <= ?")
            params.append(f["onset_to"])
        sql = f"EXISTS (SELECT 1 FROM conditions c WHERE c.patient_id = p.patient_id AND {' AND '.join(cond)})"
    elif kind == "medication":
        cond = [like_any("m.atc", f["atc_prefixes"], params)]
        if f.get("active_on"):
            cond.append("m.start_date <= ? AND (m.end_date IS NULL OR m.end_date >= ?)")
            params.extend([f["active_on"], f["active_on"]])
        if f.get("start_from"):
            cond.append("m.start_date >= ?")
            params.append(f["start_from"])
        if f.get("start_to"):
            cond.append("m.start_date <= ?")
            params.append(f["start_to"])
        sql = f"EXISTS (SELECT 1 FROM medications m WHERE m.patient_id = p.patient_id AND {' AND '.join(cond)})"
    elif kind == "observation":
        pick = f.get("pick", "latest")
        if pick == "any" or f.get("op") is None:
            cond = ["o2.loinc = ?"]
            params.append(f["loinc"])
            if f.get("op") is not None:
                cond.append(f"o2.value {OPS[f['op']]} ?")
                params.append(f["threshold"])
            for k, op in (("date_from", ">="), ("date_to", "<=")):
                if f.get(k):
                    cond.append(f"o2.date {op} ?")
                    params.append(f[k])
            sql = (f"EXISTS (SELECT 1 FROM observations o2 WHERE o2.patient_id = p.patient_id "
                   f"AND {' AND '.join(cond)})")
        else:
            sql = f"{_obs_value(f['loinc'], pick, params)} {OPS[f['op']]} ?"
            params.append(f["threshold"])
    else:
        target = "e" if unit == "encounter" else "x"
        cond = []
        if f.get("types"):
            cond.append(f"{target}.type IN ({','.join('?' * len(f['types']))})")
            params.extend(f["types"])
        if f.get("primary_icd10_prefixes"):
            cond.append(like_any(f"{target}.primary_icd10", f["primary_icd10_prefixes"], params))
        if f.get("data_holders"):
            cond.append(f"{target}.data_holder IN ({','.join('?' * len(f['data_holders']))})")
            params.extend(f["data_holders"])
        for k, op in (("start_from", ">="), ("start_to", "<=")):
            if f.get(k):
                cond.append(f"{target}.start_date {op} ?")
                params.append(f[k])
        body = " AND ".join(cond) or "1"
        sql = body if unit == "encounter" else (
            f"EXISTS (SELECT 1 FROM encounters x WHERE x.patient_id = p.patient_id AND {body})")
    return f"NOT ({sql})" if f.get("negate") else f"({sql})"


def where_sql(filters, unit, params):
    return " AND ".join(_filter_sql(f, unit, params) for f in filters) or "1"


def band_label(lo, hi):
    return f"{lo}+" if hi is None else f"{lo}-{hi}"


def _group_sql(g, unit, params):
    if g["by"] == "age_band":
        whens = []
        for lo, hi in g["bands"]:
            if hi is None:
                whens.append("WHEN p.age >= ? THEN ?")
                params.extend([lo, band_label(lo, hi)])
            else:
                whens.append("WHEN p.age BETWEEN ? AND ? THEN ?")
                params.extend([lo, hi, band_label(lo, hi)])
        return f"CASE {' '.join(whens)} END"
    if g["by"] == "data_holder" and unit == "encounter":
        return "e.data_holder"
    return f"p.{g['by']}"


def group_values(g):
    if g["by"] == "age_band":
        return [band_label(lo, hi) for lo, hi in g["bands"]]
    return data.groups()[g["by"]]


def compile_plan(plan):
    """Returns (sql, params, layout) where layout says how to read each output column."""
    validate(plan)
    unit = plan.get("unit", "patient")
    params, cols, layout = [], [], []
    groups = plan.get("group_by", [])
    for i, g in enumerate(groups):
        cols.append(f"{_group_sql(g, unit, params)} AS g{i}")
    for m in plan["measures"]:
        wp = []
        where = where_sql(m.get("where", []), unit, wp)
        if m["kind"] == "count":
            cols.append(f"SUM(CASE WHEN {where} THEN 1 ELSE 0 END) AS \"{m['name']}\"")
            params.extend(wp)
            layout.append((m["name"], "count"))
        elif m["kind"] == "percent":
            op = []
            of = where_sql(m.get("of", []), unit, op)
            cols.append(f"SUM(CASE WHEN {of} AND {where} THEN 1 ELSE 0 END) AS \"{m['name']}_num\"")
            cols.append(f"SUM(CASE WHEN {of} THEN 1 ELSE 0 END) AS \"{m['name']}_den\"")
            params.extend(op + wp + op)
            layout.append((m["name"], "percent"))
        else:
            v, vp = m["value"], []
            value = "p.age" if v.get("field") == "age" else _obs_value(v["loinc"], v.get("pick", "latest"), vp)
            cols.append(f"SUM(CASE WHEN {where} AND {value} IS NOT NULL THEN 1 ELSE 0 END) AS \"{m['name']}_n\"")
            cols.append(f"SUM(CASE WHEN {where} AND {value} IS NOT NULL THEN ROUND({value} * {SCALE}) END) "
                        f"AS \"{m['name']}_total\"")
            params.extend(wp + vp + wp + vp + vp)
            layout.append((m["name"], "mean"))
    source = "encounters e JOIN patients p ON p.patient_id = e.patient_id" if unit == "encounter" else "patients p"
    sql = f"SELECT {', '.join(cols)}\nFROM {source}\nWHERE {where_sql(plan.get('population', []), unit, params)}"
    if groups:
        sql += f"\nGROUP BY {', '.join(str(i + 1) for i in range(len(groups)))}"
    return sql, params, layout


def run(plan):
    """Executes a plan. Returns the formatted answer plus the audit trail for staff."""
    sql, params, layout = compile_plan(plan)
    db = data.connection()
    groups = plan.get("group_by", [])
    raw = {}
    for row in db.execute(sql, params):
        key = tuple(row[:len(groups)])
        if None in key:
            continue
        vals, i = {}, len(groups)
        for name, kind in layout:
            if kind == "count":
                vals[name] = (kind, row[i] or 0)
                i += 1
            elif kind == "percent":
                vals[name] = (kind, (row[i] or 0, row[i + 1] or 0))
                i += 2
            else:
                n, total = row[i] or 0, row[i + 1] or 0
                vals[name] = (kind, (Decimal(int(total)) / SCALE, n))
                i += 2
        raw[key] = vals
    empty = {name: (kind, 0 if kind == "count" else (0, 0)) for name, kind in layout}
    answer = {}
    for key in product(*(group_values(g) for g in groups)):
        cell = {name: smallcell.format_value(kind, v) for name, (kind, v) in raw.get(key, empty).items()}
        node = answer
        for k in key[:-1]:
            node = node.setdefault(k, {})
        if key:
            node[key[-1]] = cell
        else:
            answer = cell
    return {"answer": answer, "sql": render_sql(sql, params)}


def render_sql(sql, params):
    """The query with its parameters inlined, for display only."""
    out = iter(params)
    return re.sub(r"\?", lambda _: _literal(next(out)), sql)


def _literal(v):
    return str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'"
