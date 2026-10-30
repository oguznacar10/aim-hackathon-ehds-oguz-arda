"""The three ablation modes behave offline: rules ignores a key, llm normalises or flags INVALID."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gatekeeper import decision, direct, llm, reader

REPO = Path(__file__).resolve().parent.parent
R01 = json.loads((REPO / "challenge" / "requests" / "R01.json").read_text(encoding="utf-8"))


def test_keywords_mode_ignores_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(reader, "llm_reading", lambda *a, **k: pytest.fail("LLM was called"))
    assert reader.read(R01, mode="keywords")["source"] == "keywords"


def test_llm_mode_needs_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.LLMUnavailable):
        direct.decide(R01)


@pytest.mark.parametrize("answer, decision, articles", [
    ({"decision": "APPROVE_STATISTICAL", "articles": [69, "53"], "reason": "r"},
     "APPROVE_STATISTICAL", ["53", "69"]),
    ({"decision": "MAYBE", "articles": ["53"]}, "INVALID", []),
    ({"decision": "REJECT", "articles": "54"}, "INVALID", []),
])
def test_llm_mode_normalises_the_answer(monkeypatch, answer, decision, articles):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(direct, "llm_decision", lambda *a, **k: answer)
    out = direct.decide(R01)
    assert (out["decision"], out["articles"]) == (decision, articles)


def test_eval_script_rules_mode_runs_offline():
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
    proc = subprocess.run([sys.executable, "scripts/eval_decisions.py", "--mode", "rules", "--runs", "1"],
                          cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "mode=rules" in proc.stdout and "correct decisions: 10/10" in proc.stdout
    assert "not flagged for staff 0" in proc.stdout and "latency: p50" in proc.stdout


def test_openrouter_is_a_provider_with_openai_shaped_calls(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    assert llm.available_providers() == ["openrouter"]
    seen = {}

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"choices": [{"message": {"content": "{\"ok\": true}"}}]}).encode()

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["auth"] = req.get_header("Authorization")
        return Resp()

    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    assert llm.chat_json("hi", "openrouter") == {"ok": True}
    assert seen["url"].startswith("https://openrouter.ai/api/v1/")
    assert seen["auth"] == "Bearer test"


def test_key_can_come_from_secret_manager_inside_the_process(monkeypatch):
    for env in list(llm.KEY_ENV.values()) + list(llm.KEY_SECRET_ENV.values()):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY_SECRET", "projects/p1/secrets/s1")
    monkeypatch.setattr(llm, "_keys", {})
    assert llm.available_providers() == ["openrouter"]
    seen = {}

    class Proc:
        stdout = "tok\n"

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd[:2]
        return Proc()

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"payload": {"data": "c2VjcmV0LXZhbHVlCg=="}}).encode()

    def fake_urlopen(req, timeout):
        seen["url"] = req.full_url
        seen["project"] = req.get_header("X-goog-user-project")
        return Resp()

    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen)
    assert llm._key("openrouter") == "secret-value"
    assert seen["cmd"] == ["gcloud", "auth"]
    assert seen["url"].startswith("https://secretmanager.googleapis.com/v1/projects/p1/secrets/s1/")
    assert seen["project"] == "p1"


@pytest.mark.parametrize("expected, got, kind", [
    ("REJECT", "REJECT", None),
    ("REJECT", "APPROVE_STATISTICAL", "dangerous"),
    ("REJECT", "APPROVE_SPE", "dangerous"),
    ("APPROVE_STATISTICAL", "APPROVE_SPE", "dangerous"),
    ("APPROVE_STATISTICAL", "REJECT", "restrictive"),
    ("APPROVE_SPE", "APPROVE_STATISTICAL", "restrictive"),
    ("APPROVE_SPE", "REJECT", "restrictive"),
    ("APPROVE_SPE", "INVALID", "invalid"),
])
def test_error_kind_separates_over_release_from_over_restriction(expected, got, kind):
    import importlib.util
    spec = importlib.util.spec_from_file_location("eval_decisions", REPO / "scripts" / "eval_decisions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.error_kind(expected, got) == kind


def fake_answers(choice="none", noul=0.1, confidence=0.9):
    def _systemone(state, questions, backend, timeout=60):
        assert set(questions) == {"art54", "justifies"}
        assert set(state) == {"applicant", "requested_as", "purpose", "question"}
        return {"art54": {"type": "choice", "choice": choice, "confidence": confidence,
                          "probabilities": {choice: confidence}},
                "justifies": {"type": "noul", "noul": noul}}
    return _systemone


@pytest.mark.parametrize("choice, noul, prohibited, point, justifies", [
    ("none", 0.1, False, None, False),
    ("b", 0.2, True, "b", False),
    ("none", 0.8, False, None, True),
])
def test_decision_model_answers_map_to_the_two_facts(monkeypatch, choice, noul, prohibited, point, justifies):
    monkeypatch.setattr(decision, "systemone", fake_answers(choice, noul))
    out = decision.decision_reading(R01, backend="nimble", cache=False)
    assert (out["prohibited"], out["art54_point"], out["justifies_records"]) == (prohibited, point, justifies)
    assert out["source"] == "nimble" and out["confidence"] == 0.9


def test_vote_mode_escalates_when_llm_and_decision_model_disagree(monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("eval_decisions", REPO / "scripts" / "eval_decisions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.reader, "read", lambda req, **k: {
        "prohibited": False, "art54_point": None, "justifies_records": False, "evidence": "",
        "source": "openrouter", "needs_staff_review": False})
    monkeypatch.setattr(mod.decision, "systemone", fake_answers("b", 0.1))
    out = mod.decide(R01, "vote", cache=False)
    assert out["decision"] == "APPROVE_STATISTICAL" and out["needs_staff_review"] is True
    assert out["source"] == "openrouter+nimble"
