"""The three ablation modes behave offline: rules ignores a key, llm normalises or flags INVALID."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gatekeeper import direct, llm, reader

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
