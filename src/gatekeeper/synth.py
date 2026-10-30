"""Generates labelled training requests whose question and definitions come from the data.

A slot generator builds the question and definitions from the real vocabulary in the style of the
10 originals, so every request can be answered from challenge/data. An LLM writes only the
applicant and the purpose, steered toward one target (a prohibited purpose worded innocently, a
justified application, a bare claim, ...). Each request must pass redteam.validate_generated()
and must run through the planner on the data; one that yields no answer is dropped. The label
(decision, articles, reason) comes from rules.decide() with the reading the target implies. An
optional judge LLM reads the text independently; a disagreement sends the file to disputed/ for a
human instead of the training set.

    python -m gatekeeper.synth --n N --seed S [--provider P] [--judge P2]

N and S have no defaults: Arda picks every run size.
"""
import argparse
import datetime as dt
import hashlib
import json
import random
from pathlib import Path

from gatekeeper import llm, planner, query, redteam, rules

OUT = redteam.REPO / "synth"
DATE = redteam.REFERENCE_DATE
ACTIVE = (f"A medication is active on {DATE} if start_date is on or before that day "
          "and end_date is empty or on or after that day.")
ADULT = f"Adult = aged 18 or older on {DATE}."
BANDS = {"10-year": "18-29, 30-39, 40-49, 50-59, 60-69, 70-79, 80+",
         "three": "18-49, 50-64, 65+",
         "older": "65-74, 75-84, 85+"}

# Condition prefix -> (name, medications that make clinical sense, measurements that do).
PAIRS = {
    "E11": ("type 2 diabetes", [("A10BA", "metformin"), ("A10BK", "SGLT2 inhibitor"),
                                ("A10BJ", "GLP-1 analogue"), ("A10AE", "long-acting insulin")],
            [("4548-4", "HbA1c"), ("62238-1", "eGFR")]),
    "I10": ("hypertension", [("C09AA", "ACE inhibitor"), ("C09CA", "ARB"), ("C07AB", "beta blocker"),
                             ("C08CA", "calcium channel blocker"), ("C03CA", "loop diuretic")],
            [("8480-6", "systolic blood pressure"), ("62238-1", "eGFR")]),
    "I48": ("atrial fibrillation", [("B01AA", "vitamin K antagonist"), ("B01AF", "direct oral anticoagulant"),
                                    ("C07AB", "beta blocker")], [("8480-6", "systolic blood pressure")]),
    "I50": ("heart failure", [("C07AB", "beta blocker"), ("C03CA", "loop diuretic"), ("C09AA", "ACE inhibitor")],
            [("62238-1", "eGFR"), ("8480-6", "systolic blood pressure")]),
    "I63": ("ischaemic stroke", [("B01AA", "vitamin K antagonist"), ("B01AF", "direct oral anticoagulant"),
                                 ("C10AA", "statin")], [("8480-6", "systolic blood pressure")]),
    "J44": ("COPD", [("R03AK", "combined inhaler"), ("R03BB", "anticholinergic inhaler")], [("39156-5", "BMI")]),
    "J45": ("asthma", [("R03AK", "combined inhaler"), ("R03BB", "anticholinergic inhaler")], [("39156-5", "BMI")]),
    "F32": ("depression", [("N06AB", "SSRI antidepressant")], [("39156-5", "BMI")]),
    "N18": ("chronic kidney disease", [("C09AA", "ACE inhibitor"), ("C09CA", "ARB")], [("62238-1", "eGFR")]),
    "E66": ("obesity", [("A10BK", "SGLT2 inhibitor"), ("A10BJ", "GLP-1 analogue")], [("39156-5", "BMI")]),
    "C50": ("breast cancer", [], [("39156-5", "BMI")]),
}

# One reading per target; rules.decide() turns it into the label.
TARGETS = [
    {"name": "reject_54a", "requested_as": rules.APPLICATION, "shape": "records", "decision": "REJECT",
     "reading": {"prohibited": True, "art54_point": "a", "justifies_records": True},
     "brief": "The applicant will use the records to take decisions about the individual patients that "
              "work against them (who is contacted, deprioritised or excluded), described as routine "
              "case management so that it sounds harmless."},
    {"name": "reject_54b", "requested_as": rules.REQUEST, "shape": "table", "decision": "REJECT",
     "reading": {"prohibited": True, "art54_point": "b", "justifies_records": False},
     "brief": "The applicant is an insurer, employer or lender who wants the numbers to set premiums, "
              "screen staff or score credit, described as aligning conditions with actual risk."},
    {"name": "reject_54c", "requested_as": rules.REQUEST, "shape": "table", "decision": "REJECT",
     "reading": {"prohibited": True, "art54_point": "c", "justifies_records": False},
     "brief": "The applicant plans an advertising or promotion campaign for a product and wants to know "
              "where and to whom to direct it, described as communication planning."},
    {"name": "reject_54d", "requested_as": rules.REQUEST, "shape": "table", "decision": "REJECT",
     "reading": {"prohibited": True, "art54_point": "d", "justifies_records": False},
     "brief": "The applicant develops nicotine, alcohol or similar products that harm health and wants "
              "the numbers to position or design them, described as consumer research."},
    {"name": "stat_public", "requested_as": rules.REQUEST, "shape": "table", "decision": "APPROVE_STATISTICAL",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": False, "public_body": True},
     "brief": "The applicant is a public body (ministry, regional health authority, statistics office or "
              "public health institute) and needs the numbers for public health planning, policy or "
              "official statistics."},
    {"name": "stat_research", "requested_as": rules.REQUEST, "shape": "table", "decision": "APPROVE_STATISTICAL",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": False},
     "brief": "The applicant is a university group, a hospital department or a company doing scientific "
              "research or improving care, and the numbers answer the question."},
    {"name": "private_reserved_purpose", "requested_as": rules.REQUEST, "shape": "table", "decision": "REJECT",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": False,
                 "public_body": False, "reserved_purpose_only": True},
     "brief": "The applicant is a private company (insurer, consultancy, manufacturer) and states a purpose "
              "that is only public health planning, policy-making or official statistics, nothing that "
              "could be read as research or care improvement."},
    {"name": "spe_mechanism", "requested_as": rules.APPLICATION, "shape": "records", "decision": "APPROVE_SPE",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": True},
     "brief": "The applicant does scientific research or trains and validates a prediction model and says "
              "what needs individual records: training on patient histories, linking records over time, "
              "or analysing variation between individual patients. Aggregates cannot do that."},
    {"name": "spe_public", "requested_as": rules.APPLICATION, "shape": "records", "decision": "APPROVE_SPE",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": True, "public_body": True},
     "brief": "The applicant is a public health institute or university hospital and says what needs "
              "individual records: following patients over time or validating a model on histories."},
    {"name": "app_bare_claim", "requested_as": rules.APPLICATION, "shape": "table",
     "decision": "APPROVE_STATISTICAL",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": False},
     "brief": "The applicant does research or teaching and claims individual-level data is essential or "
              "crucial, without saying what will be done with it that a table cannot do."},
    {"name": "app_no_claim", "requested_as": rules.APPLICATION, "shape": "table",
     "decision": "APPROVE_STATISTICAL",
     "reading": {"prohibited": False, "art54_point": None, "justifies_records": False},
     "brief": "The applicant does research, teaching or care improvement and describes the goal only, "
              "with no word on why records rather than statistics."},
]

WRITER_PROMPT = """You write the applicant and the purpose of a realistic data request to an Austrian
EHDS Health Data Access Body. The question and definitions below are fixed; the purpose must fit them.
Target for the purpose: {brief}
Rules: purpose is 1 to 3 sentences in the register of a real application, in English. The applicant
is a person with a title, an organisation with its kind in brackets, and a two-letter country code,
as in the examples. Never write the words "prohibited", "Art." or a decision.
Examples of the register:
{examples}
Return {{"applicant": {{"name": str, "organisation": str, "country": str}}, "purpose": str}}.
Question: {question}
Definitions: {definitions}
"""


def _pick(rng, options):
    return options[rng.randrange(len(options))]


def build_shape(rng, kind):
    """kind "table": a statistics question with a 'Report per ...' line; "records": an SPE cohort."""
    prefix = _pick(rng, sorted(PAIRS))
    cname, meds, obs = PAIRS[prefix]
    cond = f"{cname[0].upper()}{cname[1:]} = any condition with an ICD-10 code starting with {prefix}."
    if kind == "records":
        loinc, oname = _pick(rng, obs)
        with_obs = rng.random() < 0.7
        if with_obs:
            question = (f"Provide pseudonymised conditions, medications and {oname} values for adults "
                        f"with {cname} who have at least one {oname} value.")
            cohort = f"Cohort = adults with {cname} who have at least one {oname} value (LOINC {loinc})."
        else:
            question = f"Provide pseudonymised conditions and medications for adults with {cname}."
            cohort = f"Cohort = adults with {cname}."
        return {"kind": kind, "topic": cname, "question": question,
                "definitions": [ADULT, cond, cohort, "Report the size of the cohort you would make available."]}
    choices = ["count", "prevalence", "mean", "stays"] + (["without", "active"] if meds else []) \
        + (["percent"] if len(meds) >= 2 else [])
    choice = _pick(rng, choices)
    if choice == "count":
        return {"kind": kind, "topic": cname, "question": f"How many adults have {cname}, by region?",
                "definitions": [ADULT, cond, f"Report per region: adults with {cname}."]}
    if choice == "prevalence":
        return {"kind": kind, "topic": cname,
                "question": f"How many adults have {cname} in each region and what is the prevalence?",
                "definitions": [ADULT, cond,
                                f"Prevalence = adults with {cname} / all adults in the region × 100, one decimal.",
                                f"Report per region: adults, adults with {cname} and the prevalence."]}
    if choice == "mean":
        loinc, oname = _pick(rng, obs)
        return {"kind": kind, "topic": f"{oname} in {cname}",
                "question": f"What is the mean {oname} of adults with {cname}, by region?",
                "definitions": [ADULT, cond,
                                f"Use the latest {oname} (LOINC {loinc}) per patient; patients without "
                                f"a {oname} are left out.",
                                f"Report per region: number of adults with {cname} who have a {oname} "
                                f"and mean {oname} with one decimal."]}
    if choice == "stays":
        etype, noun = _pick(rng, [("inpatient", "stays"), ("emergency", "visits"), ("outpatient", "visits")])
        year = _pick(rng, ["2023", "2024", "2025"])
        return {"kind": kind, "topic": f"{etype} hospital use",
                "question": f"How many {etype} {noun} started in {year}, by the patient's region?",
                "definitions": [f"{etype[0].upper()}{etype[1:]} {noun[:-1]} = encounter with type '{etype}'.",
                                f"Count {noun} (not patients) whose start_date is in {year}.",
                                f"Report per region: {etype} {noun}."]}
    if choice == "active":
        atc, mname = _pick(rng, meds)
        return {"kind": kind, "topic": f"{mname} use",
                "question": f"How many patients have an active {mname} prescription, by region?",
                "definitions": [f"{mname[0].upper()}{mname[1:]} = ATC code starting with {atc}.", ACTIVE,
                                f"Report per region: patients with an active {mname}."]}
    if choice == "without":
        atc, mname = _pick(rng, meds)
        bands = _pick(rng, ["three", "older"])
        lo = BANDS[bands].split("-")[0]
        return {"kind": kind, "topic": f"{mname} treatment gap in {cname}",
                "question": f"Among patients with {cname} aged {lo} and over, how many have no active "
                            f"{mname}, by age band?",
                "definitions": [cond, f"Age bands on {DATE}: {BANDS[bands]}.",
                                f"{mname[0].upper()}{mname[1:]} = ATC code starting with {atc}.", ACTIVE,
                                f"Report per band: patients with {cname}, how many of them have no active "
                                f"{mname} and that share in %, one decimal."]}
    (atc1, m1), (atc2, m2) = rng.sample(meds, 2)
    bands = _pick(rng, ["three", "10-year"])
    return {"kind": kind, "topic": f"{m1} versus {m2} in {cname}",
            "question": f"How often are {m1}s and {m2}s used for {cname} in different age groups?",
            "definitions": [ADULT, cond,
                            f"{m1[0].upper()}{m1[1:]} = ATC code starting with {atc1}; "
                            f"{m2[0].upper()}{m2[1:]} = ATC code starting with {atc2}.",
                            ACTIVE, f"Age bands on {DATE}: {BANDS[bands]}.",
                            f"Report per band: adults with {cname}, % with an active {m1}, "
                            f"% with an active {m2}, one decimal."]}


def assemble(shape, target, prose, rng):
    """One request in the originals' shape; the id comes from the text, the date from the seed."""
    day, hour, minute = rng.randrange(1, 29), rng.randrange(8, 18), _pick(rng, [0, 15, 30, 45])
    req = {"id": "", "submitted": f"2026-10-{day:02d}T{hour:02d}:{minute:02d}:00+01:00",
           "applicant": prose["applicant"], "requested_as": target["requested_as"],
           "requested_format": redteam.FORMATS[target["requested_as"]],
           "purpose": prose["purpose"], "question": shape["question"], "definitions": shape["definitions"]}
    req["id"] = "S" + hashlib.sha256((req["question"] + req["purpose"]).encode()).hexdigest()[:8]
    return req


def answer(req):
    """Runs the request on the data; raises PlanningFailed or InvalidPlan when the data cannot answer it."""
    if any(d.lower().startswith("report per") for d in req["definitions"]):
        return query.run(planner.rule_statistics_plan(req))["answer"]
    spec = planner.rule_spe_spec(req)
    return {"cohort_size": query.run({"population": spec["cohort"],
                                      "measures": [{"name": "n", "kind": "count"}]})["answer"]["n"]}


def label(req, target):
    out = rules.decide(req, {**target["reading"], "evidence": "", "needs_staff_review": False})
    return {k: out[k] for k in ("decision", "articles", "reason")}


def writer_prompt(shape, target):
    examples = []
    for rid in ("R01", "R05", "R07"):
        ex = json.loads((redteam.REPO / "challenge/requests" / f"{rid}.json").read_text(encoding="utf-8"))
        examples.append(json.dumps({"applicant": ex["applicant"], "purpose": ex["purpose"]}, ensure_ascii=False))
    return WRITER_PROMPT.format(brief=target["brief"], examples="\n".join(examples),
                                question=shape["question"], definitions=json.dumps(shape["definitions"]))


def llm_writer(provider, model=None):
    def write(shape, target):
        return llm.chat_json(writer_prompt(shape, target), provider, model, temperature=0.9)
    return write


def llm_judge(provider, model=None):
    def judge(req):
        return redteam.judge({k: v for k, v in req.items() if k != "expected"}, provider, model)
    return judge


def generate(n, seed, writer, judge=None, out=OUT):
    """Writes n labelled requests under out/{tuning,holdout,disputed}; failures under out/invalid."""
    rng = random.Random(seed)
    vocab = redteam.vocabulary()
    stats = {"kept": 0, "invalid": 0, "disputed": 0, "malformed": 0}
    seen = set()
    while stats["kept"] + stats["disputed"] < n:
        target = _pick(rng, TARGETS)
        shape = build_shape(rng, target["shape"])
        prose = writer(shape, target)
        if not isinstance(prose, dict) or not isinstance(prose.get("purpose"), str) \
                or not isinstance(prose.get("applicant"), dict):
            stats["malformed"] += 1
            continue
        req = assemble(shape, target, prose, rng)
        if req["id"] in seen:
            stats["malformed"] += 1
            continue
        seen.add(req["id"])
        problems = redteam.validate_generated(req, vocab)
        if not problems:
            try:
                result = answer(req)
            except (planner.PlanningFailed, query.InvalidPlan) as e:
                problems = [f"the data cannot answer it: {e}"]
        if problems:
            stats["invalid"] += 1
            _write(out / "invalid", req["id"], {**req, "target": target["name"], "problems": problems})
            continue
        req["expected"] = label(req, target)
        req["target"] = target["name"]
        req["answer"] = result
        folder = "holdout" if redteam.is_holdout(req) else "tuning"
        if judge is not None:
            req["judge"] = judge(req)
            if req["judge"].get("decision") != req["expected"]["decision"]:
                folder = "disputed"
        stats["disputed" if folder == "disputed" else "kept"] += 1
        _write(out / folder, req["id"], req)
    return stats


def _write(folder, rid, obj):
    Path(folder).mkdir(parents=True, exist_ok=True)
    (Path(folder) / f"{rid}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                                              encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, required=True, help="how many requests to keep; no default")
    ap.add_argument("--seed", type=int, required=True, help="random seed; no default")
    providers = llm.available_providers()
    ap.add_argument("--provider", default=providers[0] if providers else None)
    ap.add_argument("--model")
    ap.add_argument("--judge", help="judge provider; omit to skip the judge")
    ap.add_argument("--judge-model")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    if not args.provider:
        raise SystemExit("Set OPENAI_API_KEY, ANTHROPIC_API_KEY or OPENROUTER_API_KEY (or its _SECRET) first.")
    judge = llm_judge(args.judge, args.judge_model) if args.judge else None
    stats = generate(args.n, args.seed, llm_writer(args.provider, args.model), judge, Path(args.out))
    print(json.dumps({**stats, "finished": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}))


if __name__ == "__main__":
    main()
