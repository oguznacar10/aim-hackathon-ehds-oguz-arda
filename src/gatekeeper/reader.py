"""Turns request text into the two judgements the rules need.

The LLM reads only applicant, purpose and question, never patient data. A keyword reader runs
alongside as a second opinion; when the two disagree the decision is flagged for staff review.
"""
import hashlib
import json
import re
from pathlib import Path

from gatekeeper import llm

PROMPT_VERSION = "1"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "readings"

ART54_PATTERNS = [
    ("b", r"insurance|premium|credit scor|loan|job offer|hiring|renew contracts|employee"),
    ("c", r"advertis|marketing|campaign|promot|position the product|sales target"),
    ("d", r"nicotine|tobacco|cigarette|vape|alcohol|weapon|gambling"),
]
JUSTIFY_PATTERN = (r"aggregates are not enough|statistics are not enough|statistics (?:would|will) not"
                   r"|individual[- ]level|patient[- ]level|cannot be done with (?:aggregate|anonymi)")

PROMPT = """You assist an EHDS Health Data Access Body (Regulation (EU) 2025/327, Chapter IV).
Read the request below and answer with one JSON object:
{"prohibited": bool, "art54_point": "a"|"b"|"c"|"d"|"e"|null, "justifies_records": bool, "evidence": str}

prohibited = true only if the purpose falls under Art. 54:
(a) decisions detrimental to persons with legal, social or economic effect;
(b) decisions on job offers, less favourable terms for goods or services, insurance or credit,
    premiums, loans, or any discrimination based on health data;
(c) advertising or marketing;
(d) developing products or services that may harm individuals or public health, e.g. alcohol,
    tobacco and nicotine products, weapons, addictive products;
(e) activities against national ethics law.
Research, public health, official statistics, policy-making, teaching, improving care, and
training or testing algorithms are allowed (Art. 53), even by companies, as long as no Art. 54 use follows.

justifies_records = true only if the applicant explicitly explains why anonymised statistics or
aggregates cannot achieve the purpose and individual-level data is needed (Art. 66(3)).
Merely asking for records is not a justification.

evidence = the shortest quote from the request that supports your answer.

Worked examples:
- "align private health insurance premiums ... with their actual risk" -> prohibited, b
- "focus our physician advertising campaign" -> prohibited, c
- "match the records with our employee list ... before we renew contracts" -> prohibited, b
- "new nicotine pouch flavours ... position the products" -> prohibited, d
- "Training needs individual-level histories; aggregates are not enough." -> justifies_records
- "compare how often ACE inhibitors and ARBs are used ... Provide pseudonymised records" -> not justified

Request:
"""


def keyword_reading(request):
    text = f"{request['purpose']} {request['question']}".lower()
    point = next((p for p, pat in ART54_PATTERNS if re.search(pat, text)), None)
    just = re.search(JUSTIFY_PATTERN, text)
    return {
        "prohibited": point is not None,
        "art54_point": point,
        "justifies_records": bool(just),
        "evidence": just.group(0) if just else "",
    }


def llm_reading(request, provider, model=None):
    visible = {k: request[k] for k in ("applicant", "requested_as", "purpose", "question")}
    model = model or llm.DEFAULT_MODELS[provider]
    key = hashlib.sha256(json.dumps([PROMPT_VERSION, provider, model, visible],
                                    sort_keys=True).encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    out = llm.chat_json(PROMPT + json.dumps(visible, ensure_ascii=False), provider, model)
    reading = {
        "prohibited": bool(out.get("prohibited")),
        "art54_point": out.get("art54_point"),
        "justifies_records": bool(out.get("justifies_records")),
        "evidence": str(out.get("evidence") or ""),
    }
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(reading), encoding="utf-8")
    return reading


def read(request, provider=None, model=None):
    """LLM reading when a key is configured, keyword reading otherwise; flags disagreement."""
    kw = keyword_reading(request)
    providers = llm.available_providers()
    provider = provider or (providers[0] if providers else None)
    if provider is None:
        return {**kw, "source": "keywords", "needs_staff_review": False}
    ai = llm_reading(request, provider, model)
    disagree = (ai["prohibited"] != kw["prohibited"]
                or ai["justifies_records"] != kw["justifies_records"])
    return {**ai, "source": provider, "needs_staff_review": disagree, "second_opinion": kw}
