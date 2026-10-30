"""The only door to the patient data: an in-memory SQLite copy without opted-out patients.

Opted-out patients (Art. 71) are dropped while loading, so no query or SPE copy can reach them.
"""
import csv
import sqlite3
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "challenge" / "data"
REFERENCE_DATE = "2025-12-31"
REFERENCE_YEAR = 2025

SCHEMA = {
    "patients": ("patient_id", "sex", "birth_date", "region", "data_holder"),
    "conditions": ("patient_id", "icd10", "description", "onset_date"),
    "medications": ("patient_id", "atc", "name", "start_date", "end_date"),
    "observations": ("patient_id", "loinc", "name", "value", "unit", "date"),
    "encounters": ("encounter_id", "patient_id", "data_holder", "type", "start_date", "end_date",
                   "primary_icd10"),
}


def _rows(name):
    with open(DATA_DIR / f"{name}.csv", encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


@lru_cache(maxsize=1)
def _load():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE patients (patient_id TEXT PRIMARY KEY, sex TEXT, birth_date TEXT, "
               "region TEXT, data_holder TEXT, age INTEGER)")
    db.execute("CREATE TABLE conditions (patient_id TEXT, icd10 TEXT, description TEXT, onset_date TEXT)")
    db.execute("CREATE TABLE medications (patient_id TEXT, atc TEXT, name TEXT, start_date TEXT, "
               "end_date TEXT)")
    db.execute("CREATE TABLE observations (patient_id TEXT, loinc TEXT, name TEXT, value REAL, "
               "unit TEXT, date TEXT)")
    db.execute("CREATE TABLE encounters (encounter_id TEXT, patient_id TEXT, data_holder TEXT, "
               "type TEXT, start_date TEXT, end_date TEXT, primary_icd10 TEXT)")
    kept = set()
    for r in _rows("patients"):
        if r["opted_out"] == "true":
            continue
        kept.add(r["patient_id"])
        db.execute("INSERT INTO patients VALUES (?,?,?,?,?,?)",
                   (r["patient_id"], r["sex"], r["birth_date"], r["region"], r["data_holder"],
                    REFERENCE_YEAR - int(r["birth_date"][:4])))
    for table in ("conditions", "medications", "observations", "encounters"):
        cols = SCHEMA[table]
        rows = []
        for r in _rows(table):
            if r["patient_id"] not in kept:
                continue
            row = [r[c] or None for c in cols]
            if table == "observations":
                row[cols.index("value")] = float(r["value"])
            rows.append(row)
        db.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})", rows)
    for stmt in ("CREATE INDEX ic ON conditions(patient_id, icd10)",
                 "CREATE INDEX im ON medications(patient_id, atc)",
                 "CREATE INDEX io ON observations(patient_id, loinc, date)",
                 "CREATE INDEX ie ON encounters(patient_id)"):
        db.execute(stmt)
    db.commit()
    return db


def connection():
    return _load()


@lru_cache(maxsize=1)
def groups():
    """Every value a group can take, so empty groups still appear in an answer."""
    db = connection()
    return {
        "region": [r[0] for r in db.execute("SELECT DISTINCT region FROM patients ORDER BY 1")],
        "data_holder": [r[0] for r in db.execute("SELECT DISTINCT data_holder FROM patients ORDER BY 1")],
        "sex": ["female", "male"],
    }


@lru_cache(maxsize=1)
def catalog():
    """Code lists with labels. Vocabulary only, no patient rows; safe to show an LLM."""
    db = connection()
    return {
        "icd10": dict(db.execute("SELECT icd10, MIN(description) FROM conditions GROUP BY 1 ORDER BY 1")),
        "atc": dict(db.execute("SELECT atc, MIN(name) FROM medications GROUP BY 1 ORDER BY 1")),
        "loinc": dict(db.execute("SELECT loinc, MIN(name) FROM observations GROUP BY 1 ORDER BY 1")),
        "primary_icd10": [r[0] for r in db.execute(
            "SELECT DISTINCT primary_icd10 FROM encounters WHERE primary_icd10 IS NOT NULL ORDER BY 1")],
        "encounter_type": [r[0] for r in db.execute("SELECT DISTINCT type FROM encounters ORDER BY 1")],
        **groups(),
    }
