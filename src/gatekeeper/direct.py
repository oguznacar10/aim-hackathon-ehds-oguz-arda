"""LLM-only mode for the ablation: the model reads the brief's rules and decides end to end.

Not the shipped path. It exists so the eval can compare "LLM alone", "rules alone" and
"LLM reads, rules decide" on the same requests. Only request text is sent, never patient data.
"""
import hashlib
import json
from pathlib import Path

from gatekeeper import llm, rules

PROMPT_VERSION = "1"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "decisions"
DECISIONS = ("REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE")

PROMPT = """You are an EHDS Health Data Access Body (Regulation (EU) 2025/327, Chapter IV).
Decide the request below and answer with one JSON object:
{"decision": "REJECT"|"APPROVE_STATISTICAL"|"APPROVE_SPE", "articles": [str], "reason": str,
 "evidence": str}

Decide in this order:
1. If the purpose is prohibited by Art. 54 (decisions detrimental to persons; job offers,
   insurance, credit, premiums or discrimination; advertising or marketing; products harmful to
   health such as alcohol, tobacco and nicotine, weapons; against national ethics law):
   REJECT, articles ["54"].
2. Else if requested_as is "health data request": APPROVE_STATISTICAL, articles ["53", "69"].
3. Else if the access application explicitly explains why anonymised statistics cannot achieve
   the purpose and individual-level data is needed (Art. 66(3)): APPROVE_SPE,
   articles ["53", "66", "68", "73"].
4. Else: APPROVE_STATISTICAL, articles ["53", "66", "69"] (anonymised data suffices, Art. 66(2);
   answered with statistics, Art. 68(3) and 69).

reason = two sentences for the applicant quoting the article paragraph that applies.
evidence = the shortest quote from the request that supports the decision.

Request:
"""


def llm_decision(request, provider, model=None, cache=True):
    visible = {k: request[k] for k in ("applicant", "requested_as", "purpose", "question")}
    model = model or llm.DEFAULT_MODELS[provider]
    key = hashlib.sha256(json.dumps([PROMPT_VERSION, provider, model, visible],
                                    sort_keys=True).encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.json"
    if cache and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    out = llm.chat_json(PROMPT + json.dumps(visible, ensure_ascii=False), provider, model)
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(out), encoding="utf-8")
    return out


def decide(request, provider=None, model=None, cache=True):
    """Same result shape as rules.decide; decision is "INVALID" when the model answers off-spec."""
    rules.validate(request)
    providers = llm.available_providers()
    provider = provider or (providers[0] if providers else None)
    if provider is None:
        raise llm.LLMUnavailable("llm mode needs an API key")
    out = llm_decision(request, provider, model, cache)
    decision = out.get("decision") if isinstance(out, dict) else None
    articles = out.get("articles") if isinstance(out, dict) else None
    if decision not in DECISIONS or not isinstance(articles, list):
        decision, articles = "INVALID", []
    return {
        "decision": decision,
        "articles": sorted(str(a) for a in articles),
        "rule": None,
        "reason": str(out.get("reason") or "") if isinstance(out, dict) else "",
        "evidence": str(out.get("evidence") or "") if isinstance(out, dict) else "",
        "needs_staff_review": False,
        "source": provider,
    }
