"""Decision-model reader: typed judgments from a System One model instead of an LLM prompt.

A decision model takes the request text as state and answers named typed questions with
probabilities; it writes no prose. Two backends speak the same /v1/systemone contract:
Nimble (Bespoke Labs, 9B) locally through Ollama with no key, and Jev (TypeSafe) hosted with a key.
The rules in rules.py still make the decision; this module only supplies the two facts they need.
Only applicant, requested_as, purpose and question are sent, never patient data.
"""
import hashlib
import json
import urllib.request
from pathlib import Path

from gatekeeper import llm

QUESTION_VERSION = "1"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "decision-readings"
BACKENDS = {
    "nimble": {"url": "http://localhost:11434/v1/systemone", "model": "nimble", "key": None},
    "jev": {"url": "https://api.typesafe.ai/v1/systemone", "model": "jev-latest", "key": "typesafe"},
}

QUESTIONS = {
    "art54": {
        "type": "choice",
        "instructions": ("Under Art. 54 of the EHDS Regulation (EU) 2025/327, is the applicant's stated purpose "
                         "for using health data prohibited, and under which point? Research, public health, "
                         "statistics, policy-making, teaching, improving care and training or testing algorithms "
                         "are allowed purposes (Art. 53), also for companies, unless a prohibited use follows."),
        "criteria": {
            "none": "The purpose is allowed; no prohibited use is stated or implied",
            "a": "Taking decisions detrimental to a natural person with legal, social or economic effect",
            "b": "Decisions on job offers, less favourable terms, insurance or credit, premiums, loans, "
                 "or any discrimination based on health data",
            "c": "Advertising or marketing",
            "d": "Developing products or services that may harm individuals or public health, such as alcohol, "
                 "tobacco and nicotine products, weapons, addictive products",
            "e": "Activities in conflict with national ethics law",
        },
    },
    "justifies": {
        "type": "noul",
        "instructions": ("Does the applicant explicitly explain why anonymised statistics or aggregates cannot "
                         "achieve the purpose and individual-level data is needed (Art. 66(3))? Merely asking "
                         "for records, or describing a research goal, is not such an explanation."),
    },
}


def systemone(state, questions, backend, timeout=60):
    cfg = BACKENDS[backend]
    headers = {"Content-Type": "application/json"}
    if cfg["key"]:
        headers["Authorization"] = f"Bearer {llm.key_for(cfg['key'])}"
    body = {"model": cfg["model"], "state": state, "questions": questions}
    req = urllib.request.Request(cfg["url"], data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["answers"]


def decision_reading(request, backend="nimble", cache=True):
    """Same shape as reader.read() output, plus the model's probabilities and confidence."""
    visible = {k: request[k] for k in ("applicant", "requested_as", "purpose", "question")}
    key = hashlib.sha256(json.dumps([QUESTION_VERSION, backend, BACKENDS[backend]["model"], visible],
                                    sort_keys=True).encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.json"
    if cache and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    answers = systemone(visible, QUESTIONS, backend)
    point = answers["art54"]["choice"]
    reading = {
        "prohibited": point != "none",
        "art54_point": None if point == "none" else point,
        "justifies_records": answers["justifies"]["noul"] >= 0.5,
        "evidence": "",
        "source": backend,
        "needs_staff_review": False,
        "probabilities": {"art54": answers["art54"].get("probabilities", {}),
                          "justifies": answers["justifies"]["noul"]},
        "confidence": answers["art54"].get("confidence"),
    }
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(reading), encoding="utf-8")
    return reading
