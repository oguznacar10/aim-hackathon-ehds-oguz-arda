"""Statistics, small-cell rule, opt-outs and the SPE, through the pipeline and module interfaces.

Assertions compare plain ints and formatted values only, so no patient row reaches test output.
"""
import csv
import json
import sqlite3
from pathlib import Path

import pytest

from gatekeeper import data, pipeline, query, smallcell, spe

CHALLENGE = Path(__file__).resolve().parent.parent / "challenge"
EXPECTED = json.loads((CHALLENGE / "requests" / "expected.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def load(rid):
    return json.loads((CHALLENGE / "requests" / f"{rid}.json").read_text(encoding="utf-8"))


def csv_rows(name):
    with open(CHALLENGE / "data" / f"{name}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def flat(node):
    if isinstance(node, dict):
        return [x for v in node.values() for x in flat(v)]
    return [node]


@pytest.mark.parametrize("rid", ["R01", "R03", "R07", "R08", "R09"])
def test_statistical_answers_match_expected(rid):
    out = pipeline.handle(load(rid))
    for group, exp in EXPECTED[rid]["answer"].items():
        have = flat(out["answer"][group])
        for v in (exp.values() if isinstance(exp, dict) else [exp]):
            assert v in have, (rid, group)


def test_spe_cohort_size_and_contents():
    out = pipeline.handle(load("R05"))
    assert out["answer"] == {"cohort_size": EXPECTED["R05"]["answer"]["cohort_size"]}
    manifest = out["staff"]["spe"]
    assert set(manifest["tables"]) == {"conditions", "medications", "observations"}
    db = sqlite3.connect(Path(__file__).resolve().parent.parent / manifest["workspace"])
    opted_out = {r["patient_id"] for r in csv_rows("patients") if r["opted_out"] == "true"}
    ids = {r[0] for r in db.execute("SELECT patient_id FROM cohort")}
    assert len(ids) == manifest["cohort_size"]
    assert len(ids & opted_out) == 0
    for table in manifest["tables"]:
        outside = db.execute(f"SELECT COUNT(*) FROM {table} WHERE patient_id NOT IN "
                             "(SELECT patient_id FROM cohort)").fetchone()[0]
        assert outside == 0, table
    loincs = [r[0] for r in db.execute("SELECT DISTINCT loinc FROM observations")]
    assert loincs == ["4548-4"]


def test_spe_download_is_blocked():
    pipeline.handle(load("R05"))
    with pytest.raises(spe.DownloadBlocked):
        spe.download("R05", "conditions")


def test_rejected_and_patient_level_requests_get_no_data():
    for rid in ("R02", "R04", "R06", "R10"):
        assert pipeline.handle(load(rid))["answer"] is None, rid


def test_opted_out_patients_never_loaded():
    total = data.connection().execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    assert total == 20000 - 839


def test_small_cell_rule():
    assert smallcell.format_value("count", 0) == "<10"
    assert smallcell.format_value("count", 9) == "<10"
    assert smallcell.format_value("count", 10) == 10
    assert smallcell.format_value("percent", (9, 100)) == "suppressed"
    assert smallcell.format_value("percent", (9, 9)) == "suppressed"
    assert smallcell.format_value("percent", (10, 0)) == "suppressed"
    assert smallcell.format_value("percent", (1, 8 * 10)) == "suppressed"
    assert smallcell.format_value("percent", (25, 1000)) == 2.5
    assert smallcell.format_value("mean", (90, 9)) == "suppressed"


def test_round_half_up():
    assert smallcell.round1("0.25") == 0.3
    assert smallcell.round1("2.35") == 2.4
    assert smallcell.format_value("percent", (10, 16)) == 62.5
    assert smallcell.format_value("percent", (13, 80)) == 16.3


def test_every_group_appears_even_if_empty():
    out = query.run({"population": [{"kind": "region", "values": ["Wien"]}],
                     "group_by": [{"by": "region"}],
                     "measures": [{"name": "n", "kind": "count"}]})
    assert set(out["answer"]) == set(data.groups()["region"])
    assert out["answer"]["Tirol"] == {"n": "<10"}


def test_plan_rejects_anything_that_is_not_a_code():
    with pytest.raises(query.InvalidPlan):
        query.validate({"population": [{"kind": "condition", "icd10_prefixes": ["E11' OR 1=1 --"]}],
                        "measures": [{"name": "n", "kind": "count"}]})
    with pytest.raises(query.InvalidPlan):
        query.validate({"measures": [{"name": "n", "kind": "sql", "text": "SELECT 1"}]})


def new_request(rid, question, definitions):
    return {"id": rid, "applicant": {"name": "Test", "organisation": "University hospital research unit"},
            "requested_as": "health data request", "purpose": "We study care quality for a research project.",
            "question": question, "definitions": definitions}


def test_unseen_inpatient_stays_by_main_diagnosis_and_hospital():
    req = new_request("T01", "How many inpatient stays for hip fracture started in 2025, by hospital?", [
        "Hip fracture stay = inpatient encounter whose primary_icd10 starts with S72.",
        "Count stays (not patients) whose start_date is in 2025.",
        "Report per hospital: hip fracture stays.",
    ])
    out = pipeline.handle(req)
    kept = {r["patient_id"] for r in csv_rows("patients") if r["opted_out"] != "true"}
    truth = {h: 0 for h in data.groups()["data_holder"]}
    for e in csv_rows("encounters"):
        if (e["patient_id"] in kept and e["type"] == "inpatient" and e["primary_icd10"].startswith("S72")
                and e["start_date"].startswith("2025")):
            truth[e["data_holder"]] += 1
    assert {h: flat(v) for h, v in out["answer"].items()} == {
        h: [smallcell.format_value("count", n)] for h, n in truth.items()}


def test_unseen_patients_by_hospital_with_age_and_condition():
    req = new_request("T02", "How many patients aged 65 or older have heart failure, by hospital?", [
        "Older adult = aged 65 or older on 31 December 2025.",
        "Heart failure = any condition with an ICD-10 code starting with I50.",
        "Report per hospital: older adults with heart failure.",
    ])
    out = pipeline.handle(req)
    hf = {c["patient_id"] for c in csv_rows("conditions") if c["icd10"].startswith("I50")}
    truth = {h: 0 for h in data.groups()["data_holder"]}
    for p in csv_rows("patients"):
        if p["opted_out"] != "true" and 2025 - int(p["birth_date"][:4]) >= 65 and p["patient_id"] in hf:
            truth[p["data_holder"]] += 1
    assert {h: flat(v) for h, v in out["answer"].items()} == {
        h: [smallcell.format_value("count", n)] for h, n in truth.items()}
