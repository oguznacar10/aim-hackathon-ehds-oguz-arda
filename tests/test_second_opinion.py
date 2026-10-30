import json
from pathlib import Path

from gatekeeper import pipeline

REQ = Path(__file__).resolve().parents[1] / "challenge" / "requests"


def _load(rid):
    return json.loads((REQ / f"{rid}.json").read_text(encoding="utf-8"))


def test_disagreeing_decision_model_escalates(monkeypatch):
    monkeypatch.setenv("GATEKEEPER_SECOND_OPINION", "jev")
    monkeypatch.setattr(pipeline.decision, "decision_reading",
                        lambda request, backend: {"prohibited": True, "art54_point": "c",
                                                  "justifies_records": False, "source": backend})
    out = pipeline.handle(_load("R03"))
    assert out["decision"] == "APPROVE_STATISTICAL"
    assert out["needs_staff_review"] is True
    assert out["reading"]["second_opinion"]["source"] == "jev"


def test_agreeing_decision_model_does_not_escalate(monkeypatch):
    monkeypatch.setenv("GATEKEEPER_SECOND_OPINION", "jev")
    monkeypatch.setattr(pipeline.decision, "decision_reading",
                        lambda request, backend: {"prohibited": False, "art54_point": None,
                                                  "justifies_records": False, "source": backend})
    out = pipeline.handle(_load("R03"))
    assert out["needs_staff_review"] is False


def test_decision_model_down_never_blocks(monkeypatch):
    monkeypatch.setenv("GATEKEEPER_SECOND_OPINION", "jev")

    def down(request, backend):
        raise OSError("connection refused")
    monkeypatch.setattr(pipeline.decision, "decision_reading", down)
    out = pipeline.handle(_load("R03"))
    assert out["decision"] == "APPROVE_STATISTICAL"
    assert "jev unavailable" in out["reading"]["second_opinion_error"]
