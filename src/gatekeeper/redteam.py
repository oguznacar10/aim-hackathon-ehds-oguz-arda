"""Attacker/judge loop that grows a labelled test set of new requests.

Attacker (one LLM) writes tricky requests with an intended decision. Judge (ideally a different
provider) labels each one independently. Agreements become test cases, split into a tuning set and
a held-out exam set; disagreements go to a disputed folder for a human to settle.

Every generated request is checked against the data dictionary before it is kept: only codes that
exist in challenge/data, the fixed requested_format wording, and definitions in the originals' style.

    python -m gatekeeper.redteam --n 10 --focus "hidden marketing"
"""
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from gatekeeper import llm, rules

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "redteam"
DATA = REPO / "challenge" / "data"
EXAMPLES = (REPO / "challenge/requests/R03.json", REPO / "challenge/requests/R05.json")
DECISIONS = ("REJECT", "APPROVE_STATISTICAL", "APPROVE_SPE")
FORMATS = {rules.REQUEST: "anonymised statistics", rules.APPLICATION: "pseudonymised records"}
REFERENCE_DATE = "31 December 2025"
CODE_PATTERNS = {"icd10": r"\b[A-Z]\d{2}(?:\.\d{1,2})?\b", "atc": r"\b[A-Z]\d{2}[A-Z]{1,2}(?:\d{2})?\b",
                 "loinc": r"\b\d{4,5}-\d\b"}


def vocabulary():
    """Distinct codes with a readable name, plus regions and hospitals, read from the synthetic data."""
    def pairs(file, code, name=None):
        with (DATA / file).open(newline="", encoding="utf-8") as f:
            rows = {(r[code], r[name] if name else "") for r in csv.DictReader(f)}
        return sorted(rows)
    with (DATA / "patients.csv").open(newline="", encoding="utf-8") as f:
        patients = list(csv.DictReader(f))
    return {
        "icd10": pairs("conditions.csv", "icd10", "description"),
        "atc": pairs("medications.csv", "atc", "name"),
        "loinc": pairs("observations.csv", "loinc", "name"),
        "regions": sorted({r["region"] for r in patients}),
        "data_holders": sorted({r["data_holder"] for r in patients}),
    }


def vocabulary_text(vocab):
    lines = [f"Reference date for ages and active medications: {REFERENCE_DATE}.",
             "ICD-10 codes in conditions.csv (the only ones that exist): "
             + ", ".join(f"{c} {n}" for c, n in vocab["icd10"]),
             "ATC codes in medications.csv (the only ones that exist): "
             + ", ".join(f"{c} {n}" for c, n in vocab["atc"]),
             "LOINC codes in observations.csv (the only ones that exist): "
             + ", ".join(f"{c} {n}" for c, n in vocab["loinc"]),
             "Regions: " + ", ".join(vocab["regions"]),
             "Hospitals (data holders): " + ", ".join(vocab["data_holders"]),
             "Encounters: inpatient, outpatient or emergency visits 2023 to 2025 with a primary ICD-10."]
    return "\n".join(lines)


def validate_generated(req, vocab):
    """Problems that make a generated request unrealistic or unanswerable with the data; empty = fine."""
    problems = []
    try:
        rules.validate(req)
    except rules.InvalidRequest as e:
        return [str(e)]
    want = FORMATS[req["requested_as"]]
    if req.get("requested_format") != want:
        problems.append(f"requested_format must be '{want}' for a {req['requested_as']}")
    if len(req["definitions"]) < 3:
        problems.append("fewer than 3 definitions; the originals have 4 to 6")
    text = " ".join([req["purpose"], req["question"], *req["definitions"]])
    if not any(d.lower().startswith("report") for d in req["definitions"]):
        problems.append("no 'Report ...' definition saying what to return")
    for kind, pattern in CODE_PATTERNS.items():
        known = [c for c, _ in vocab[kind]]
        for token in sorted(set(re.findall(pattern, text))):
            if not any(code.startswith(token) for code in known):
                problems.append(f"{kind} code {token} is not in the data")
    return problems

ATTACKER_PROMPT = """You red-team an EHDS Health Data Access Body. Write {n} new, realistic data
requests that are hard to classify correctly. Focus: {focus}.
Mix: purposes prohibited by Art. 54 but worded innocently; allowed research that sounds suspicious;
access applications that do or do not explain why aggregated statistics are not enough; private
companies claiming public-sector purposes (Art. 53(2): public health, policy-making and official
statistics are reserved for public bodies); decisions about individual people (Art. 54(a)).
Vary applicants, countries and wording.

The data that exists, and nothing else. Every code you mention must come from these lists:
{vocabulary}

Hard rules for realism:
- requested_format is exactly "anonymised statistics" for a health data request and exactly
  "pseudonymised records" for a health data access application.
- 4 to 6 definitions in the style of the examples: cohort by code prefix, age or active-medication
  rule naming the reference date, groups or bands, and a last definition starting with "Report"
  that says what to return and the rounding.
- A request that cannot be answered from these files is a bad request.

Example requests:
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
2. Art. 53(2): a private applicant whose purpose fits only public health, policy-making or
   official statistics (nothing that can be read as research, teaching, care improvement or
   algorithm work) -> "REJECT". A public body may claim those purposes.
3. requested_as "health data request" -> "APPROVE_STATISTICAL".
4. "health data access application" whose text says what will be done with individual records
   that statistics cannot do (train or validate a model on histories, link records, follow
   patients over time, compare individual responses) and whose "Report" definition is not itself
   counts, percentages or means per group -> "APPROVE_SPE". Asking for records, describing a
   research goal, or calling individual data "essential" is not such an explanation.
5. Any other access application -> "APPROVE_STATISTICAL".

Request:
{request}
"""


def attack(n, focus, provider, examples, vocab, model=None):
    prompt = ATTACKER_PROMPT.format(n=n, focus=focus, vocabulary=vocabulary_text(vocab),
                                    example="\n".join(json.dumps(e, indent=1, ensure_ascii=False)
                                                       for e in examples))
    out = llm.chat_json(prompt, provider, model, temperature=0.9)
    return out.get("requests", [])


def judge(request, provider, model=None):
    visible = {k: v for k, v in request.items() if k != "intended"}
    return llm.chat_json(JUDGE_PROMPT.format(request=json.dumps(visible, ensure_ascii=False)), provider, model)


def is_holdout(request):
    digest = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).digest()
    return digest[0] % 4 == 0


def run(n, focus, attacker, judge_provider, example_paths, attacker_model=None, judge_model=None):
    examples = [json.loads(Path(p).read_text(encoding="utf-8")) for p in example_paths]
    vocab = vocabulary()
    stats = {"agreed": 0, "disputed": 0, "malformed": 0, "invalid": 0}
    for req in attack(n, focus, attacker, examples, vocab, attacker_model):
        intended = (req.get("intended") or {}).get("decision")
        if intended not in DECISIONS or "purpose" not in req:
            stats["malformed"] += 1
            continue
        rid = "G" + hashlib.sha256(req["purpose"].encode()).hexdigest()[:8]
        req = {**req, "id": rid}
        problems = validate_generated(req, vocab)
        if problems:
            stats["invalid"] += 1
            (OUT / "invalid").mkdir(parents=True, exist_ok=True)
            (OUT / "invalid" / f"{rid}.json").write_text(
                json.dumps({**req, "problems": problems}, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8")
            continue
        verdict = judge(req, judge_provider, judge_model)
        req = {**req, "judge": verdict}
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
    ap.add_argument("--example", action="append",
                    help="example request file; repeatable; default: R03 (statistics) and R05 (records)")
    args = ap.parse_args()
    if not args.attacker or not args.judge:
        raise SystemExit("Set OPENAI_API_KEY, ANTHROPIC_API_KEY or OPENROUTER_API_KEY first.")
    print(json.dumps(run(args.n, args.focus, args.attacker, args.judge, args.example or EXAMPLES,
                         args.attacker_model, args.judge_model)))


if __name__ == "__main__":
    main()
