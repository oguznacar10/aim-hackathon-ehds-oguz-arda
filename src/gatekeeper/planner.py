"""Turns a request's plain-English definitions into a query plan (statistics) or an SPE spec.

Two planners write the same JSON: a rule planner for the definition style the challenge uses,
and an LLM planner that sees only request text and the code vocabulary, never patient rows.
"""
import hashlib
import json
import re
from pathlib import Path

from gatekeeper import data, llm, query, spe

PROMPT_VERSION = "4"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "plans"
GROUP_WORDS = [
    ("age_band", r"age band|band|age group"),
    ("region", r"region|federal state|state"),
    ("data_holder", r"hospital|data holder|data_holder|klinik"),
    ("sex", r"\bsex\b|gender"),
]
RECORD_WORDS = [
    ("conditions", r"condition|diagnos"),
    ("medications", r"medication|prescription|drug"),
    ("observations", r"observation|measurement|lab|values?\b|hba1c|bmi|blood pressure|egfr"),
    ("encounters", r"encounter|visit|stay|admission"),
    ("patients", r"demograph|birth|\bsex\b|\bage\b"),
]


class PlanningFailed(ValueError):
    pass


def _year_range(text):
    m = re.search(r"\bin (\d{4})\b", text)
    return (f"{m.group(1)}-01-01", f"{m.group(1)}-12-31") if m else (None, None)


def _codes_after(text, label):
    m = re.search(label + r"[^.;]*?start(?:ing|s) with ([A-Z0-9.]+(?:(?:,| or|, or) [A-Z0-9.]+)*)", text, re.I)
    return [c.rstrip(".") for c in re.findall(r"[A-Z][A-Z0-9.]*", m.group(1))] if m else None


def _lookup(name, vocab):
    words = name.lower().split()
    return [code for code, label in vocab.items() if all(w in label.lower() for w in words)]


def _term(name, rhs, active_on):
    """One definition's right-hand side to a filter, or None if it is not a cohort term."""
    low = rhs.lower()
    cat = data.catalog()
    m = re.search(r"aged (\d+) or older", low)
    if m:
        return {"kind": "age", "min": int(m.group(1))}
    m = re.search(r"aged (\d+) or younger|younger than (\d+)", low)
    if m:
        return {"kind": "age", "max": int(m.group(1)) if m.group(1) else int(m.group(2)) - 1}
    m = re.search(r"sex '?(female|male)'?", low)
    if m:
        return {"kind": "sex", "value": m.group(1)}
    if "encounter" in low or "primary_icd10" in low or "main diagnosis" in low:
        f = {"kind": "encounter"}
        types = [t for t in cat["encounter_type"] if re.search(rf"'?{t}'?", low)]
        if types:
            f["types"] = types
        codes = _codes_after(rhs, r"(?:primary_icd10|main diagnosis)")
        if codes:
            f["primary_icd10_prefixes"] = codes
        return f
    codes = _codes_after(rhs, r"ICD-10")
    if codes:
        return {"kind": "condition", "icd10_prefixes": codes}
    codes = _codes_after(rhs, r"ATC")
    if codes:
        return {"kind": "medication", "atc_prefixes": codes, "active_on": active_on}
    m = re.search(r"LOINC ([\w\-]+)", rhs)
    if m:
        return {"kind": "observation", "loinc": m.group(1)}
    if re.search(r"condition|diagnos", low):
        found = _lookup(name, cat["icd10"])
        if found:
            return {"kind": "condition", "icd10_prefixes": found}
    if re.search(r"medication|prescri|drug", low):
        found = _lookup(name, cat["atc"])
        if found:
            return {"kind": "medication", "atc_prefixes": found, "active_on": active_on}
    return None


def _parse(request):
    defs = [d.strip() for d in request["definitions"]]
    text = " ".join(defs)
    active_on = data.REFERENCE_DATE if re.search(r"medication is active", text, re.I) else None
    terms, percents, extra = {}, {}, {"report": None, "cohort": None, "bands": None, "unit": "patient",
                                       "year": (None, None), "picks": {}}
    for d in defs:
        for m in re.finditer(r"(?:latest|last|earliest|first|any)?\s*([A-Za-z0-9][\w\-]*)\s+(?:values?\s+)?"
                             r"\(LOINC\s+([\w\-]+)\)", d):
            terms.setdefault(m.group(1), {"kind": "observation", "loinc": m.group(2)})
        m = re.search(r"\b(latest|last|earliest|first)\b[^.]*?\(LOINC\s+([\w\-]+)\)", d, re.I)
        if m:
            extra["picks"][m.group(2)] = "earliest" if m.group(1).lower() in ("earliest", "first") else "latest"
        if re.match(r"age bands?\b", d, re.I):
            extra["bands"] = [[int(lo), int(hi) if hi else None]
                              for lo, hi in re.findall(r"(\d+)\s*(?:-\s*(\d+)|\+)", d.split(":", 1)[-1])]
            continue
        if re.match(r"report\b", d, re.I):
            extra["report"] = d
            continue
        if re.search(r"count (?:stays|encounters|visits|admissions)|\(not patients\)", d, re.I):
            extra["unit"] = "encounter"
            extra["year"] = _year_range(d)
            continue
        for part in d.split(";"):
            if "=" not in part:
                continue
            name, rhs = (s.strip() for s in part.split("=", 1))
            if name.lower() == "cohort":
                extra["cohort"] = rhs
                continue
            if re.search(r"\s/\s", rhs):
                num, den = rhs.split("/", 1)
                percents[name] = (num, den)
                continue
            f = _term(name, rhs, active_on)
            if f:
                terms[name] = f
    for f in terms.values():
        if f["kind"] == "observation" and f["loinc"] in extra["picks"]:
            f["pick"] = extra["picks"][f["loinc"]]
    return terms, percents, extra


def _pattern(name):
    words = [re.escape(w) for w in name.lower().split()]
    words[-1] = words[-1] + r"(?:s|es)?"
    return r"\b" + r"\s+".join(words) + r"\b"


def _mentioned(phrase, terms):
    """[(name, negated)] for every term named in the phrase, in order."""
    low, found = phrase.lower(), []
    for name in sorted(terms, key=len, reverse=True):
        m = re.search(_pattern(name), low)
        if m and not any(m.start() >= s and m.end() <= e for _, _, s, e in found):
            neg = bool(re.search(r"\b(no|without|not|never)\b", low[:m.start()]))
            found.append((name, neg, m.start(), m.end()))
    return [(n, neg) for n, neg, _, _ in sorted(found, key=lambda x: x[2])]


def _measure_filter(f, negate):
    f = {k: v for k, v in f.items() if k != "pick"} if f["kind"] == "observation" else dict(f)
    if f.get("kind") == "medication" and f.get("active_on") is None:
        f.pop("active_on")
    return {**f, "negate": True} if negate else f


def _clean(f):
    f = dict(f)
    if f.get("kind") == "medication" and f.get("active_on") is None:
        f.pop("active_on")
    if f.get("kind") == "observation":
        f.pop("pick", None)
    return f


def _slug(phrase):
    phrase = re.sub(r"^(?:the|their|that|its|number of|how many of them(?: have| are)?|how many)\s+", "",
                    phrase.strip(), flags=re.I)
    phrase = re.sub(r"\s+in %$", " %", phrase)
    s = re.sub(r"[^a-z0-9%]+", "_", phrase.lower()).strip("_").replace("%", "pct")
    return s[:48] or "value"


def _groups_from(text, bands):
    out = []
    hits = sorted((m.start(), g) for g, pat in GROUP_WORDS for m in [re.search(pat, text, re.I)] if m)
    for _, g in hits:
        if g == "age_band" and not bands:
            continue
        if g in [x["by"] for x in out]:
            continue
        out.append({"by": "age_band", "bands": bands} if g == "age_band" else {"by": g})
    return out


def _split_measures(body, terms):
    protected = body
    names = sorted(terms, key=len, reverse=True)
    for i, n in enumerate(names):
        protected = re.sub(_pattern(n), lambda m, i=i: f"@{i}@" if " " in m.group(0) else m.group(0),
                           protected, flags=re.I)
    parts = [p.strip() for p in re.split(r",\s*(?:and\s+)?|\s+and\s+", protected) if p.strip()]
    restore = []
    for p in parts:
        p = re.sub(r"@(\d+)@", lambda m: names[int(m.group(1))], p)
        p = re.sub(r"\s*(?:with |rounded to |to )?one decimal\w*$", "", p, flags=re.I).strip()
        if p and not re.fullmatch(r"(?:rounded|one decimal|in %)", p, re.I):
            restore.append(p)
    return restore


def rule_statistics_plan(request):
    terms, percents, extra = _parse(request)
    report = extra["report"]
    if not report or ":" not in report:
        raise PlanningFailed("no 'Report per ...:' definition to build statistics from")
    head, body = report.rstrip(". ").split(":", 1)
    if re.search(r"each patient|patient id|birth date", report, re.I):
        raise PlanningFailed("the request asks for patient-level rows; statistics cannot report those")
    unit = extra["unit"]
    measure_terms = set()
    for num, den in percents.values():
        num_terms = {n for n, _ in _mentioned(num, terms)}
        den_terms = {n for n, _ in _mentioned(den, terms)}
        measure_terms |= num_terms - den_terms
    for name, f in terms.items():
        if f["kind"] in ("medication", "observation"):
            measure_terms.add(name)
        if f["kind"] == "encounter" and unit == "patient":
            measure_terms.add(name)
    population = [_clean(f) for n, f in terms.items() if n not in measure_terms]
    if unit == "encounter":
        start, end = extra["year"]
        enc = [f for f in population if f["kind"] == "encounter"]
        if not enc:
            population.append({"kind": "encounter"})
            enc = [population[-1]]
        if start:
            enc[0]["start_from"], enc[0]["start_to"] = start, end
    regions = [r for r in data.groups()["region"] if r in request["question"] or r in report]
    holders = [h for h in data.groups()["data_holder"] if h in request["question"] or h in report]
    groups = _groups_from(head, extra["bands"])
    if regions and "region" not in [g["by"] for g in groups]:
        population.append({"kind": "region", "values": regions})
    if holders and "data_holder" not in [g["by"] for g in groups]:
        population.append({"kind": "data_holder", "values": holders})

    measures, last_where = [], []
    for phrase in _split_measures(body, terms):
        mentioned = _mentioned(phrase, terms)
        where = [_measure_filter(terms[n], neg) for n, neg in mentioned if n in measure_terms]
        pct_def = next((n for n in percents if re.search(_pattern(n), phrase, re.I)), None)
        if pct_def:
            num, den = percents[pct_def]
            where = [_measure_filter(terms[n], neg) for n, neg in _mentioned(num, terms) if n in measure_terms]
            of = [_measure_filter(terms[n], neg) for n, neg in _mentioned(den, terms) if n in measure_terms]
            measures.append({"name": _slug(phrase), "kind": "percent", "where": where, "of": of})
        elif re.search(r"%|\bshare\b|percent|proportion|\brate\b", phrase, re.I):
            measures.append({"name": _slug(phrase), "kind": "percent", "where": where or last_where})
        elif re.search(r"\bmean\b|\baverage\b", phrase, re.I):
            obs = [n for n, _ in mentioned if terms[n]["kind"] == "observation"]
            if obs:
                value = {"loinc": terms[obs[0]]["loinc"], "pick": terms[obs[0]].get("pick", "latest")}
                where = [w for w in where if not (w["kind"] == "observation" and w["loinc"] == value["loinc"])]
            elif re.search(r"\bage\b", phrase, re.I):
                value = {"field": "age"}
            else:
                raise PlanningFailed(f"cannot tell what to average in '{phrase}'")
            measures.append({"name": _slug(phrase), "kind": "mean", "where": where, "value": value})
        else:
            measures.append({"name": _slug(phrase), "kind": "count", "where": where})
            last_where = where
    names = set()
    for m in measures:
        while m["name"] in names:
            m["name"] += "_2"
        names.add(m["name"])
    if not measures:
        raise PlanningFailed("no measures found in the report definition")
    return query.validate({"unit": unit, "population": population, "group_by": groups, "measures": measures})


def rule_spe_spec(request):
    terms, _, extra = _parse(request)
    scope = extra["cohort"] or request["question"]
    cohort = [{**_clean(terms[n]), "negate": True} if neg else _clean(terms[n])
              for n, neg in _mentioned(scope, terms)]
    if not cohort:
        cohort = [_clean(f) for f in terms.values() if f["kind"] in ("age", "sex", "condition")]
    question = request["question"]
    records = []
    for table, pat in RECORD_WORDS:
        if re.search(pat, question, re.I):
            rec = {"table": table}
            if table == "observations":
                loincs = [terms[n]["loinc"] for n, _ in _mentioned(question, terms)
                          if terms[n]["kind"] == "observation"]
                if loincs:
                    rec["loinc"] = loincs
            records.append(rec)
    if not records:
        raise PlanningFailed("the application does not name any record type to copy")
    return spe.validate({"cohort": cohort, "records": records})


PROMPT = """You translate a health data request into a JSON plan for an EHDS Health Data Access Body.
You never see patient data. Use only the codes in the vocabulary below; the definitions in the
request are authoritative and override your own medical knowledge.
Reference date 2025-12-31; age = 2025 minus birth year. A medication is active on a date if
start_date <= date and (end_date empty or >= date): use "active_on" only when the request says active.
Observations: use the latest value per patient unless the request says otherwise.

Return {"statistics": <plan>} when MODE is statistics, {"spe": <spec>} when MODE is spe.

<plan> language:
%s
Filters (every field except "kind" is optional unless marked required; add "negate": true for
"without" / "not"):
  {"kind": "age", "min": int, "max": int}            inclusive, age in years
  {"kind": "sex", "value": "female" | "male"}        required value
  {"kind": "region", "values": [names]}              names from the vocabulary
  {"kind": "data_holder", "values": [names]}         the hospital
  {"kind": "condition", "icd10_prefixes": ["E11"], "onset_from": date, "onset_to": date}
  {"kind": "medication", "atc_prefixes": ["A10B"], "active_on": date, "start_from": date, "start_to": date}
  {"kind": "observation", "loinc": "4548-4", "pick": "latest" | "earliest" | "any",
   "op": ">" | ">=" | "<" | "<=" | "=", "threshold": number, "date_from": date, "date_to": date}
  {"kind": "encounter", "types": [types], "primary_icd10_prefixes": [codes], "data_holders": [names],
   "start_from": date, "start_to": date}
Codes are prefixes: "E11" matches E11 and every E11.x code. Dates are "YYYY-MM-DD".
Example (not one of the requests). Definitions: "Asthma: ICD-10 starting with J45. Inhaled
corticosteroid: ATC starting with R03BA, active on 31 Dec 2025. Report per region: women aged 40
or older with asthma; percentage of them without an active inhaled corticosteroid." Plan:
{"unit": "patient", "population": [{"kind": "sex", "value": "female"}, {"kind": "age", "min": 40},
 {"kind": "condition", "icd10_prefixes": ["J45"]}], "group_by": [{"by": "region"}],
 "measures": [{"name": "women_with_asthma", "kind": "count", "where": []},
 {"name": "without_ics_pct", "kind": "percent", "where": [{"kind": "medication",
 "atc_prefixes": ["R03BA"], "active_on": "2025-12-31", "negate": true}], "of": []}]}
Measures: exactly one per item in the report definition, in its order, nothing added. A plain
group size ("patients with X", "women with asthma") is a count with "where": []. "Without",
"no" and "not" become "negate": true on the filter. Do not repeat population filters inside
"where", and do not add filters or dates the definitions do not state.
For "percent", "where" is the numerator condition and "of" the denominator condition, both
within the population and group. "population", "where" and "of" are always JSON lists of
filters, even for a single filter. Every count, percent and mean the request asks to report is
one measure, in the order the request lists them. A mean is over patients in population+where
who have the value. Group by age_band only with the bands the request gives. Use "unit":
"encounter" only when the request counts stays/visits rather than patients; then encounter
filters apply to the counted encounter itself.

<spec> language: {"cohort": [filter, ...], "records": [{"table": "conditions"|"medications"|
"observations"|"encounters"|"patients", "loinc": [codes]?}, ...]}. Copy only the record types the
request names; restrict observations to the named measurements.

Vocabulary (code: label): %s

MODE: %s
Request:
"""


REPAIR = """

Your previous answer was rejected by the validator.
Previous answer: %s
Validator error: %s
Return the corrected JSON object only."""


def _check(out, mode):
    if not isinstance(out, dict):
        raise query.InvalidPlan("the answer must be a JSON object")
    return query.validate(out.get("statistics")) if mode == "statistics" else spe.validate(out.get("spe") or {})


def llm_plan(request, mode, provider, model=None):
    visible = {k: request[k] for k in ("question", "definitions", "requested_as")}
    model = model or llm.DEFAULT_MODELS[provider]
    key = hashlib.sha256(json.dumps([PROMPT_VERSION, mode, provider, model, visible],
                                    sort_keys=True).encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.json"
    if cached.exists():
        out = json.loads(cached.read_text(encoding="utf-8"))
    else:
        prompt = PROMPT % (query.__doc__, json.dumps(data.catalog(), ensure_ascii=False), mode)
        prompt += json.dumps(visible, ensure_ascii=False)
        out = llm.chat_json(prompt, provider, model)
        try:
            _check(out, mode)
        except query.InvalidPlan as e:
            out = llm.chat_json(prompt + REPAIR % (json.dumps(out, ensure_ascii=False), e), provider, model)
    plan = _check(out, mode)
    if not cached.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(out), encoding="utf-8")
    return plan
