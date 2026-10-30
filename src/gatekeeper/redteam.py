"""Attacker/judge loop that grows a labelled test set of new requests.

Attacker (one LLM) writes tricky requests with an intended decision. Judge (ideally a different
provider) labels each one independently. Agreements become test cases, split into a tuning set and
a held-out exam set; disagreements go to a disputed folder for a human to settle.

    python -m gatekeeper.redteam --n 10 --focus "hidden marketing"
"""
import argparse
import hashlib
import json
from pathlib import Path

from gatekeeper import llm

OUT = Path(__file__).resolve().parents[2] / "redteam"
DECISIONS = ("REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE")

ATTACKER_PROMPT = """You red-team an EHDS Health Data Access Body. Write {n} new, realistic data
requests that are hard to classify correctly. Focus: {focus}.
Mix: purposes prohibited by Art. 54 but worded innocently; allowed research that sounds suspicious;
access applications that do or do not explain why aggregated statistics are not enough; private
companies claiming public-sector purposes. Vary applicants, countries and wording.
The data available: Austrian patients with ICD-10 conditions, ATC medications, LOINC observations,
encounters, region and hospital. Write definitions in plain English like the example.

Example request:
{example}

Label each request with the decision the law gives, in this order:
1. Purpose prohibited by Art. 54 (detrimental decisions about people; jobs, insurance, credit,
   discrimination; advertising or marketing; harmful products such as tobacco, nicotine, alcohol,
   weapons; against national ethics law) -> "REJECT". Nothing else is a reason to reject:
   commercial applicants, genetics or sensitive topics are allowed if the purpose itself is.
2. requested_as "health data request" -> "APPROVE_STATISTICAL".
3. "health data access application" whose text explicitly says why anonymised statistics cannot
   achieve the purpose -> "APPROVE_SPE".
4. Any other access application -> "APPROVE_STATISTICAL".

Return {{"requests": [ ... ]}}, each item having the example's fields plus
"intended": {{"decision": "REJECT"|"APPROVE_STATISTICAL"|"APPROVE_SPE", "why": str}}.
"""

JUDGE_PROMPT = """You are a senior lawyer at an EHDS Health Data Access Body. Decide this request
strictly in this order and answer {{"decision": ..., "why": str}}:
1. Purpose prohibited by Art. 54 (detrimental decisions; jobs, insurance, credit, discrimination;
   advertising or marketing; harmful products such as tobacco, nicotine, alcohol, weapons;
   against national ethics law) -> "REJECT".
2. requested_as "health data request" -> "APPROVE_STATISTICAL".
3. "health data access application" that explicitly explains why anonymised statistics cannot
   achieve the purpose -> "APPROVE_SPE". Asking for records, or describing a research goal, is
   not such an explanation; the text has to say why aggregates are not enough.
4. Any other access application -> "APPROVE_STATISTICAL".

Request:
{request}
"""


def attack(n, focus, provider, example, model=None):
    out = llm.chat_json(ATTACKER_PROMPT.format(n=n, focus=focus, example=json.dumps(example, indent=1)),
                        provider, model, temperature=0.9)
    return out.get("requests", [])


def judge(request, provider, model=None):
    visible = {k: v for k, v in request.items() if k != "intended"}
    return llm.chat_json(JUDGE_PROMPT.format(request=json.dumps(visible, ensure_ascii=False)), provider, model)


def is_holdout(request):
    digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).digest()
    return digest[0] % 4 == 0


def run(n, focus, attacker, judge_provider, example_path, attacker_model=None, judge_model=None):
    example = json.loads(Path(example_path).read_text(encoding="utf-8"))
    stats = {"agreed": 0, "disputed": 0, "malformed": 0}
    for req in attack(n, focus, attacker, example, attacker_model):
        intended = (req.get("intended") or {}).get("decision")
        if intended not in DECISIONS or "purpose" not in req:
            stats["malformed"] += 1
            continue
        verdict = judge(req, judge_provider, judge_model)
        rid = "G" + hashlib.sha256(req["purpose"].encode()).hexdigest()[:8]
        req = {**req, "id": rid, "judge": verdict}
        if verdict.get("decision") == intended:
            folder = "holdout" if is_holdout(req) else "tuning"
            req["expected"] = intended
            stats["agreed"] += 1
        else:
            folder = "disputed"
            stats["disputed"] += 1
        (OUT / folder).mkdir(parents=True, exist_ok=True)
        (OUT / folder / f"{rid}.json").write_text(json.dumps(req, indent=2, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
    return stats


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--focus", default="a mix of all tricky cases")
    providers = llm.available_providers()
    ap.add_argument("--attacker", default=providers[0] if providers else None)
    ap.add_argument("--judge", default=providers[-1] if providers else None)
    ap.add_argument("--attacker-model", help="e.g. openai/gpt-4o-mini on OpenRouter")
    ap.add_argument("--judge-model", help="a different family, e.g. anthropic/claude-3.5-haiku on OpenRouter")
    ap.add_argument("--example", default=str(Path(__file__).resolve().parents[2] / "challenge/requests/R05.json"))
    args = ap.parse_args()
    if not args.attacker or not args.judge:
        raise SystemExit("Set OPENAI_API_KEY, ANTHROPIC_API_KEY or OPENROUTER_API_KEY first.")
    print(json.dumps(run(args.n, args.focus, args.attacker, args.judge, args.example,
                         args.attacker_model, args.judge_model)))


if __name__ == "__main__":
    main()
