"""Secure processing environment: one SQLite workspace per approved access application.

Only the selected patients and the record types the request names are copied in, with their
pseudonymised patient IDs. Nothing personal leaves: download() always refuses (Art. 73(2)).
"""
import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from gatekeeper import data, query

ROOT = Path(__file__).resolve().parents[2] / "spe"
TABLES = {"patients", "conditions", "medications", "observations", "encounters"}
ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class DownloadBlocked(PermissionError):
    pass


def validate(spec):
    """spec = {"cohort": [filter, ...], "records": [{"table": str, "loinc": [..]?, ...}, ...]}"""
    query.validate({"population": spec.get("cohort", []),
                    "measures": [{"name": "cohort_size", "kind": "count"}]})
    records = spec.get("records")
    if not isinstance(records, list) or not records:
        raise query.InvalidPlan("an SPE needs at least one record type")
    for r in records:
        if not isinstance(r, dict) or r.get("table") not in TABLES:
            raise query.InvalidPlan(f"unknown record type: {r!r}")
        for key in ("loinc", "icd10_prefixes", "atc_prefixes"):
            if r.get(key) is not None:
                query.check_codes(r[key], key)
    return spec


def _workspace(request_id):
    if not ID.match(request_id):
        raise ValueError(f"request id not usable as an SPE name: {request_id!r}")
    return ROOT / request_id


def create(request_id, spec):
    """Builds the workspace and returns its manifest (counts only, no rows)."""
    validate(spec)
    folder = _workspace(request_id)
    folder.mkdir(parents=True, exist_ok=True)
    db_path = folder / "workspace.sqlite"
    if db_path.exists():
        db_path.unlink()
    params = []
    where = query.where_sql(spec.get("cohort", []), "patient", params)
    cohort_sql = f"SELECT p.patient_id FROM patients p WHERE {where}"
    ids = [r[0] for r in data.connection().execute(cohort_sql, params)]

    with closing(sqlite3.connect(db_path)) as out:
        out.execute("CREATE TABLE cohort (patient_id TEXT PRIMARY KEY)")
        out.executemany("INSERT INTO cohort VALUES (?)", [(i,) for i in ids])
        src = data.connection()
        src.execute("DROP TABLE IF EXISTS temp.spe_cohort")
        src.execute("CREATE TEMP TABLE spe_cohort (patient_id TEXT PRIMARY KEY)")
        src.executemany("INSERT INTO temp.spe_cohort VALUES (?)", [(i,) for i in ids])
        tables = {}
        for rec in spec["records"]:
            table = rec["table"]
            cols = list(data.SCHEMA[table])
            cond, p = ["t.patient_id IN (SELECT patient_id FROM temp.spe_cohort)"], []
            if rec.get("loinc") and table == "observations":
                cond.append(f"t.loinc IN ({','.join('?' * len(rec['loinc']))})")
                p.extend(rec["loinc"])
            if rec.get("icd10_prefixes") and table == "conditions":
                cond.append(query.like_any("t.icd10", rec["icd10_prefixes"], p))
            if rec.get("atc_prefixes") and table == "medications":
                cond.append(query.like_any("t.atc", rec["atc_prefixes"], p))
            rows = src.execute(f"SELECT {', '.join('t.' + c for c in cols)} FROM {table} t "
                               f"WHERE {' AND '.join(cond)}", p).fetchall()
            out.execute(f"CREATE TABLE {table} ({', '.join(cols)})")
            out.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})", rows)
            tables[table] = len(rows)
        src.execute("DROP TABLE temp.spe_cohort")
        out.commit()
    manifest = {
        "request_id": request_id,
        "cohort_size": len(ids),
        "tables": tables,
        "workspace": str(db_path.relative_to(ROOT.parent)),
        "cohort_sql": query.render_sql(cohort_sql, params),
        "downloads": "blocked (Art. 73(2)): only non-personal results may leave, after staff review",
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    return manifest


def download(request_id, table):
    """Every download attempt is refused and logged."""
    folder = _workspace(request_id)
    folder.mkdir(parents=True, exist_ok=True)
    entry = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "request_id": request_id, "table": str(table), "result": "blocked"}
    with open(folder / "audit.log", "a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    raise DownloadBlocked(
        f"Download of '{table}' from SPE {request_id} refused: personal data may not leave the "
        "secure processing environment (Art. 73(2)). Export anonymised results through staff review.")
