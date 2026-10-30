import json
from pathlib import Path

import pytest

from gatekeeper import data, planner, query, spe

REQUESTS = Path(__file__).resolve().parent.parent / "challenge" / "requests"
STATISTICAL = ["R01", "R03", "R07", "R08", "R09"]


def load(rid):
    return json.loads((REQUESTS / f"{rid}.json").read_text(encoding="utf-8"))


def test_each_hospital_holds_only_its_own_patients():
    nodes = data.nodes()
    assert set(nodes) == set(data.holders()) and len(nodes) == 3
    total = 0
    for holder, db in nodes.items():
        held = {r[0] for r in db.execute("SELECT DISTINCT data_holder FROM patients")}
        assert held == {holder}
        total += db.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    assert total == data.connection().execute("SELECT COUNT(*) FROM patients").fetchone()[0]


@pytest.mark.parametrize("rid", STATISTICAL)
def test_federated_answer_equals_central_answer(rid, monkeypatch):
    plan = planner.rule_statistics_plan(load(rid))
    federated = query.run(plan)["answer"]
    monkeypatch.setattr(data, "nodes", lambda: {"all": data.connection()})
    assert federated == query.run(plan)["answer"]


def test_spe_cohort_is_collected_from_every_hospital():
    request = load("R05")
    manifest = spe.create("R05", planner.rule_spe_spec(request))
    assert set(manifest["hospitals"]) == set(data.holders())
    assert sum(manifest["hospitals"].values()) == manifest["cohort_size"] == 1152


def test_hospital_summary_adds_up():
    rows = data.summary()
    assert [r["hospital"] for r in rows] == list(data.holders())
    assert sum(r["patients"] for r in rows) == 19161
    assert sum(r["opted_out_excluded"] for r in rows) == 839
    assert all(r["records"] > 0 for r in rows)
