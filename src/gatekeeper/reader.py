"""Turns request text into the judgements the rules need.

The LLM reads only applicant, purpose and question, never patient data. A keyword reader runs
alongside as a second opinion; when the two disagree the decision is flagged for staff review.
"""
import hashlib
import json
import re
from pathlib import Path

from gatekeeper import llm, rules

PROMPT_VERSION = "2"
CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache" / "readings"

ART54_PATTERNS = [
    ("b", r"insurance|premium|credit scor|loan|job offer|hiring|renew contracts|employee"),
    ("c", r"advertis|marketing|campaign|promot|position the product|sales target"),
    ("d", r"nicotine|tobacco|cigarette|vape|alcohol|weapon|gambling"),
]
JUSTIFY_PATTERN = (r"aggregates are not enough|statistics are not enough|statistics (?:would|will) not"
                   r"|individual[- ]level|patient[- ]level|cannot be done with (?:aggregate|anonymi)")
MECHANISM_PATTERN = (r"train|validat|\blink|follow(?:-| )?up|over time|longitudinal|per[- ]patient"
                     r"|variation|individual responses|between (?:individual )?patients")
PUBLIC_BODY_PATTERN = (r"ministry|ministerium|federal|national |statistics office|statistik|agency|authority"
                       r"|government|municipal|public health (?:institute|office|service)")
RESERVED_PATTERN = (r"official statistics|policy-?making|annual health report|regulatory"
                    r"|public health (?:strateg|surveillance|programme|program|planning|policy)")
ALLOWED_PATTERN = (r"research|stud(?:y|ies)|train|validat|model|algorithm|teach|education"
                   r"|improv\w* (?:care|treatment|delivery)|quality programme|prevention advice")

PROMPT = """You assist an EHDS Health Data Access Body (Regulation (EU) 2025/327, Chapter IV).
Read the request below and answer with one JSON object:
{"prohibited": bool, "art54_point": "a"|"b"|"c"|"d"|"e"|null, "public_body": bool,
 "reserved_purpose_only": bool, "justifies_records": bool, "evidence": str}

prohibited = true only if the purpose falls under Art. 54:
(a) decisions detrimental to persons with legal, social or economic effect;
(b) decisions on job offers, less favourable terms for goods or services, insurance or credit,
    premiums, loans, or any discrimination based on health data;
(c) advertising or marketing;
(d) developing products or services that may harm individuals or public health, e.g. alcohol,
    tobacco and nicotine products, weapons, addictive products;
(e) activities against national ethics law.
Research, teaching, improving care, and training or testing algorithms are allowed for any applicant,
companies included (Art. 53(1)(d), (e), (f)). Public health, policy-making and official statistics
(Art. 53(1)(a), (b), (c)) are allowed only for public sector bodies and Union bodies, or a third party
acting on their behalf (Art. 53(2)).

public_body = true if the applicant is a public sector body (a ministry, agency, authority, national
statistics office, public health institute) or acts on behalf of one.
reserved_purpose_only = true if the stated purpose fits only public health, policy-making or official
statistics and cannot reasonably be read as research, teaching, improving care or algorithm work.

justifies_records = true only if the applicant names what will be done with individual records that
anonymised statistics cannot do: train or validate a model on patient histories, link records to
another dataset, follow patients over time, or compare responses between individual patients
(Art. 66(3)). "Essential", "crucial" or "we need individual data" alone is a claim, not a
justification, and merely asking for records is not one either.

evidence = the shortest quote from the request that supports your answer.

Worked examples:
- "align private health insurance premiums ... with their actual risk" -> prohibited, b
- "focus our physician advertising campaign" -> prohibited, c
- "match the records with our employee list ... before we renew contracts" -> prohibited, b
- "new nicotine pouch flavours ... position the products" -> prohibited, d
- "Training needs individual-level histories; aggregates are not enough." -> justifies_records
- "compare how often ACE inhibitors and ARBs are used ... Provide pseudonymised records" -> not justified
- "individual-level records are essential to create effective care plans" -> not justified (a claim only)
- insurer, "improve public health strategies in the region" -> reserved_purpose_only, not public_body
- "National statistics office", "Official statistics on hospital use" -> public_body, reserved_purpose_only
- "university research group", "study regional differences ... prevention programme" -> not reserved_purpose_only

Request:
"""


def keyword_reading(request):
    text = f"{request['purpose']} {request['question']}".lower()
    applicant = json.dumps(request["applicant"], ensure_ascii=False).lower()
    point = next((p for p, pat in ART54_PATTERNS if re.search(pat, text)), None)
    just = re.search(JUSTIFY_PATTERN, text)
    reserved = re.search(RESERVED_PATTERN, text)
    reading = {
        "prohibited": point is not None,
        "art54_point": point,
        "public_body": bool(re.search(PUBLIC_BODY_PATTERN, applicant)),
        "reserved_purpose_only": bool(reserved and not re.search(ALLOWED_PATTERN, text)),
        "justifies_records": bool(just and re.search(MECHANISM_PATTERN, text)),
        "evidence": just.group(0) if just else "",
    }
    if rules.blocked_by_53_2(reading):
        reading["evidence"] = reserved.group(0)
    return reading


def llm_reading(request, provider, model=None, cache=True):
    visible = {k: request[k] for k in ("applicant", "requested_as", "purpose", "question")}
    model = model or llm.DEFAULT_MODELS[provider]
    key = hashlib.sha256(json.dumps([PROMPT_VERSION, provider, model, visible],
                                    sort_keys=True).encode()).hexdigest()
    cached = CACHE_DIR / f"{key}.json"
    if cache and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    out = llm.chat_json(PROMPT + json.dumps(visible, ensure_ascii=False), provider, model)
    reading = {
        "prohibited": bool(out.get("prohibited")),
        "art54_point": out.get("art54_point"),
        "public_body": bool(out.get("public_body")),
        "reserved_purpose_only": bool(out.get("reserved_purpose_only")),
        "justifies_records": bool(out.get("justifies_records")),
        "evidence": str(out.get("evidence") or ""),
    }
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(reading), encoding="utf-8")
    return reading


def read(request, provider=None, model=None, mode="auto", cache=True):
    """LLM reading when a key is configured, keyword reading otherwise; flags disagreement.

    mode="keywords" forces the keyword reader even when a key is set (the "rules" ablation).
    """
    kw = keyword_reading(request)
    providers = llm.available_providers()
    provider = provider or (providers[0] if providers else None)
    if provider is None or mode == "keywords":
        return {**kw, "source": "keywords", "needs_staff_review": False}
    try:
        ai = llm_reading(request, provider, model, cache)
    except (llm.LLMUnavailable, ValueError, OSError) as e:
        return {**kw, "source": "keywords", "needs_staff_review": True,
                "llm_error": f"{provider} unavailable, keyword reading used: {e}"[:300]}
    disagree = ai["prohibited"] != kw["prohibited"] or (
        not ai["prohibited"] and rules.blocked_by_53_2(ai) != rules.blocked_by_53_2(kw)) or (
        not ai["prohibited"] and request["requested_as"] == rules.APPLICATION
        and ai["justifies_records"] != kw["justifies_records"])
    return {**ai, "source": provider, "needs_staff_review": disagree, "second_opinion": kw}
