"""The 10 challenge requests are the regression suite for the decision rules."""
import json
from pathlib import Path

import pytest

from gatekeeper import reader, rules

REQUESTS = Path(__file__).resolve().parent.parent / "challenge" / "requests"
EXPECTED = json.loads((REQUESTS / "expected.json").read_text(encoding="utf-8"))


def load(rid):
    return json.loads((REQUESTS / f"{rid}.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.parametrize("rid", sorted(EXPECTED))
def test_challenge_decision(rid):
    result = rules.decide(load(rid), reader.read(load(rid)))
    assert result["decision"] == EXPECTED[rid]["decision"]
    assert result["articles"] == EXPECTED[rid]["articles"]
    assert result["reason"]


def reading(prohibited=False, justifies=False, review=False):
    return {"prohibited": prohibited, "art54_point": None, "justifies_records": justifies,
            "evidence": "", "needs_staff_review": review}


def test_prohibited_beats_everything():
    req = load("R05")
    assert rules.decide(req, reading(prohibited=True, justifies=True))["decision"] == "REJECT"


def test_statistics_request_never_gets_spe():
    req = load("R01")
    assert rules.decide(req, reading(justifies=True))["decision"] == "APPROVE_STATISTICAL"


def test_staff_review_flag_is_passed_through():
    assert rules.decide(load("R09"), reading(review=True))["needs_staff_review"] is True


def test_disagreement_between_readers_flags_review(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(reader, "llm_reading",
                        lambda req, provider, model=None, cache=True: {
                            "prohibited": True, "art54_point": "a", "justifies_records": False,
                            "evidence": "x"})
    out = reader.read(load("R01"))
    assert out["prohibited"] is True
    assert out["needs_staff_review"] is True


@pytest.mark.parametrize("broken", [
    {"id": "X"},
    {**load("R01"), "requested_as": "please send everything"},
    {**load("R01"), "definitions": "not a list"},
])
def test_invalid_request_is_refused(broken):
    with pytest.raises(rules.InvalidRequest):
        rules.decide(broken, reading())


def test_llm_outage_falls_back_to_keywords_and_flags_review(monkeypatch):
    def down(*_args, **_kwargs):
        raise OSError("HTTP Error 429: Too Many Requests")
    monkeypatch.setattr(reader.llm, "available_providers", lambda: ["openrouter"])
    monkeypatch.setattr(reader, "llm_reading", down)
    reading = reader.read(load("R02"))
    assert reading["source"] == "keywords"
    assert reading["needs_staff_review"] is True
    assert "429" in reading["llm_error"]
    assert rules.decide(load("R02"), reading)["decision"] == "REJECT"


def test_llm_client_retries_rate_limits(monkeypatch):
    import io
    import urllib.error

    from gatekeeper import llm
    calls = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(req, timeout):
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return Resp(b'{"choices": [{"message": {"content": "{\\"ok\\": true}"}}]}')
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(llm, "BACKOFF_S", 0)
    monkeypatch.setattr(llm.urllib.request, "urlopen", urlopen)
    assert llm.chat_json("json please", "openrouter") == {"ok": True}
    assert len(calls) == 3


def private_reserved_request():
    """A private insurer asking, as a health data request, for official statistics (Art. 53(2))."""
    return {**load("R07"), "id": "T53",
            "applicant": {"name": "Markus Gruber", "organisation": "Alpenland Versicherung AG, public affairs",
                          "country": "AT"}}


def test_private_applicant_with_reserved_purpose_is_refused_under_53():
    req = private_reserved_request()
    out = rules.decide(req, reader.read(req))
    assert (out["decision"], out["articles"], out["needs_staff_review"]) == ("REJECT", ["53"], True)
    assert "53(2)" in out["reason"]


def test_public_body_keeps_the_reserved_purpose():
    out = rules.decide(load("R07"), reader.read(load("R07")))
    assert (out["decision"], out["articles"]) == ("APPROVE_STATISTICAL", ["53", "69"])


def test_private_applicant_approved_when_purpose_also_fits_research():
    req = {**private_reserved_request(),
           "purpose": "Official statistics on hospital use, as input to our research study of regional differences."}
    assert rules.decide(req, reader.read(req))["decision"] == "APPROVE_STATISTICAL"


def test_readers_disagreeing_on_53_2_flag_review(monkeypatch):
    monkeypatch.setattr(reader.llm, "available_providers", lambda: ["openrouter"])
    monkeypatch.setattr(reader, "llm_reading",
                        lambda req, provider, model=None, cache=True: {
                            "prohibited": False, "art54_point": None, "public_body": False,
                            "reserved_purpose_only": True, "justifies_records": False, "evidence": "x"})
    out = reader.read(load("R07"))
    assert out["needs_staff_review"] is True


def test_records_justified_but_table_requested_falls_to_rule_4():
    req = {**load("R09"), "purpose": load("R09")["purpose"]
           + " We will train a model on individual-level histories; aggregates are not enough."}
    assert reader.read(req)["justifies_records"] is True
    out = rules.decide(req, reader.read(req))
    assert (out["decision"], out["articles"], out["rule"]) == ("APPROVE_STATISTICAL", ["53", "66", "69"], 4)
    assert "66(2)" in out["reason"]


def test_bare_assertion_is_not_a_justification():
    req = {**load("R09"), "purpose": load("R09")["purpose"] + " Individual-level records are essential."}
    assert reader.read(req)["justifies_records"] is False


def test_r05_report_line_is_not_a_table():
    assert rules.report_is_table(load("R05")["definitions"]) is False
    assert rules.report_is_table(load("R09")["definitions"]) is True
