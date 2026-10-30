# AIM Hackathon EHDS - Oguz & Arda

**.Gatekeeper**: a Health Data Access Body for the European Health Data Space (Regulation (EU) 2025/327, Chapter IV). Built at the AIM Healthcare Hackathon Vienna, 29-30 October 2026, Track 3.

An applicant submits a health data request. The app, automatically:
1. decides `REJECT`, `APPROVE_STATISTICAL` or `APPROVE_SPE` and cites the articles,
2. computes anonymised statistics under the small-cell rule, without opted-out patients,
3. or copies only the selected patients' records into a secure processing environment (SPE), where every download attempt is refused and logged,
4. and shows the decision as a notice to the applicant and as a case file to staff, who can confirm or overrule it.

The applicant does not choose between statistics and records. The system decides from what the request says.

## Run it

Needs Python 3.10 or newer. No other packages are needed to run the app (pytest and ruff only for the tests).

**Windows PowerShell** (one line at a time):
```
git clone https://github.com/oguznacar10/aim-hackathon-ehds-oguz-arda
cd aim-hackathon-ehds-oguz-arda
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-ci.txt
$env:OPENROUTER_API_KEY = "sk-or-..."
python scripts/serve.py
```
If `Activate.ps1` is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

**macOS / Linux:**
```
git clone https://github.com/oguznacar10/aim-hackathon-ehds-oguz-arda
cd aim-hackathon-ehds-oguz-arda
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-ci.txt
export OPENROUTER_API_KEY=sk-or-...
python scripts/serve.py
```

Open http://127.0.0.1:8000. In **Applicant**, load one of the 10 sample requests (or type a new one) and submit. In **Staff**, click "Decide the 10 sample requests" to fill the queue. Stop the server with Ctrl+C.

Without an API key everything still runs, offline: a keyword reader and a rule planner replace the LLM. They handle the wording of the 10 sample requests but are weaker on new wording. The rule planner refuses a request whose measure no definition explains, instead of guessing numbers.

Other commands:
```
python scripts/eval_metrics.py          # the five challenge metrics on the 10 requests
python scripts/eval_decisions.py --set tuning   # decisions on the AI-written red-team requests
python -m gatekeeper.synth --n N --seed S --max-attempts M   # generate labelled training requests
pytest -q                               # regression tests, never call an LLM
```

## Architecture

```
 request (JSON or web form)
        |
        v
 reader.py   LLM reads applicant, purpose and question only  -->  2 judgements:
             + keyword reader as second opinion                   prohibited? (Art. 54)
             disagreement or LLM outage -> staff review           records justified? (Art. 66(3))
        |
        v
 rules.py    fixed code, the brief's 4 steps -> decision + articles + reason
        |
        +-- REJECT -------------------------------> notice, no data released
        |
        +-- APPROVE_STATISTICAL
        |     planner.py  definitions -> JSON query plan (LLM, rule plan as cross-check)
        |     query.py    validates the plan, compiles parameterised SQL
        |     data.py     one SQLite database per hospital, opted-out patients dropped at load;
        |                 the query runs in each, only totals come back and are added up
        |     smallcell.py  every value leaves through one function (<10, suppressed, rounding)
        |
        +-- APPROVE_SPE
              planner.py  definitions -> SPE spec (cohort + record types)
              spe.py      one SQLite workspace per application, only the cohort's named records;
                          download() always refuses and writes audit.log (Art. 73(2))
        |
        v
 web.py + static/   stdlib HTTP server; applicant notice, staff case file, blocked download
```

| Component | File | What it does |
|---|---|---|
| Reader | `src/gatekeeper/reader.py` | LLM answers two yes/no questions about the request text, with the evidence sentence. A keyword reader gives a second opinion; any disagreement sets `needs_staff_review`. |
| Decision rules | `src/gatekeeper/rules.py` | Deterministic: Art. 54 purpose → reject; health data request → statistics; private applicant whose purpose fits only public health, policy-making or official statistics → reject under Art. 53(2); access application that names what records are needed for and does not ask for a table per group → SPE; otherwise statistics. Attaches the articles. The LLM never decides. |
| Planner | `src/gatekeeper/planner.py` | Turns the plain-English definitions into a JSON query plan or SPE spec. The LLM sees only question, definitions and the code list (ICD-10, ATC, LOINC labels), never patient rows. A rule planner writes the same plan; different numbers flag staff review. |
| Query engine | `src/gatekeeper/query.py` | A plan never contains SQL. Every field is validated, then compiled to parameterised SQL. Staff see plan and SQL. |
| Data access | `src/gatekeeper/data.py` | The only door to the CSVs. Loads one in-memory SQLite database per hospital and drops opted-out patients (Art. 71) and all their rows. |
| Small-cell rule | `src/gatekeeper/smallcell.py` | Counts below 10 → `<10`; percentages and means on fewer than 10 → `suppressed`; every requested group shown; halves rounded up. |
| SPE | `src/gatekeeper/spe.py` | Copies the cohort and only the record types the question names into `spe/<id>/workspace.sqlite`. Downloads are refused server-side and logged. |
| Pipeline | `src/gatekeeper/pipeline.py` | `handle(request)`: read, decide, then statistics or SPE. |
| Web app | `src/gatekeeper/web.py`, `src/gatekeeper/static/` | Python standard library HTTP server, plain HTML/CSS/JS, no build step. Patient rows never reach the browser. |
| LLM-only mode | `src/gatekeeper/direct.py` | Not the shipped path. The LLM reads the brief's rules and decides end to end, so `eval_decisions.py` can compare LLM alone, rules alone and LLM reads, rules decide. |
| Training requests | `src/gatekeeper/synth.py` | Builds the question and definitions from the real vocabulary of the data; an LLM writes only applicant and purpose. Labels come from `rules.decide()`; a judge LLM that disagrees sends the request to a human. |
| Red-team loop | `src/gatekeeper/redteam.py` | One LLM writes tricky new requests with an intended decision, a second LLM from another vendor labels them independently. Agreements become test cases, disagreements go to a human (`redteam/REVIEW.md`). |

**Models and services.** One OpenRouter key (`OPENROUTER_API_KEY`). Reader and planner use `openai/gpt-4o` at temperature 0; answers are cached by prompt version, model and request text, so the same request gets the same answer. For the red team, `openai/gpt-4o` writes and `anthropic/claude-haiku-4.5` judges. We picked gpt-4o after comparing planners on the 6 approved requests: gpt-4o 6/6, gpt-4.1-mini 4/6, gpt-4o-mini 2/6. OpenAI and Anthropic keys also work (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). Only request text is ever sent to an LLM.

**Federated, one database per hospital.** Each hospital (`data_holder`: Klinikum Nord, Süd, West) has its own database with only its own patients. A query runs in each hospital and only totals come back: counts, numerators and denominators, value sums. The access body adds them up and applies the small-cell rule once, on the totals. Suppressing per hospital first would hide counts that are safe in total. An SPE collects its cohort from every hospital. In this prototype the three databases run in one process; in production each would sit behind its own service.

## Metric results on the 10 requests

From `python scripts/eval_metrics.py` with `OPENROUTER_API_KEY` set, run on 30 October 2026 with the LLM cache emptied first, so the first of the 3 runs made real LLM calls:

| Metric | Target | Ours |
|---|---|---|
| Correct decisions | 10 of 10 | 10 of 10 |
| Correct numbers | 6 of 6 | 6 of 6 |
| Privacy leaks | 0 | 0 |
| Consistency over 3 runs | 10 of 10 | 10 of 10 |
| Slowest request | under 60 s | 12.7 s |

Runs 2 and 3 reuse the cached LLM answers, so consistency is partly guaranteed by the cache. The offline mode (no key) also scores 10/10, 6/6, 0 leaks, 10/10, slowest 1.0 s (re-run on the current `main`). The run with the key above was made before the planner changes in PRs #13 and #21 and has not been repeated since.

On the 8 AI-written red-team requests where writer and judge agreed: 8 of 8 correct decisions, 8 of 8 consistent over 3 runs, slowest 1.3 s.

### On the 36 generated requests (synth run 1)

`scripts/eval_decisions.py --set synth/tuning` and `--set synth/holdout`, 30 October 2026, 3 runs with `--no-cache` for the key-bound modes (every run a live gpt-4o call through OpenRouter), 3 runs for the offline modes. The 36 requests are built from the data's vocabulary, labelled by the rules and checked by an independent judge; 4 more with a contestable Art. 53(2) label sit in `synth/disputed/` and are not scored.

| Mode | Tuning (25) | Holdout (11) | Dangerous, not flagged | Escalated to staff |
|---|---|---|---|---|
| rules (keyword reader, offline) | 14 | 4 | 21 of 75, 9 of 33 | 0 |
| nimble (local reader, offline) | 22 | 9 | 9 of 75, 3 of 33 | 0 |
| llm (gpt-4o decides alone, ablation) | 23 | 10 | 6 of 75, 3 of 33 | 0 |
| hybrid (gpt-4o reads, rules decide, shipped) | 25 | 11 | 0 | 37 of 75, 21 of 33 |
| vote (gpt-4o reads, Nimble second opinion) | 25 | 11 | 0 | 37 of 75, 21 of 33 |

Every mode gave the same decision in all 3 runs. The model alone would have granted records to two applications that only call individual data "essential" and approved an insurer's policy-consultation request that Art. 53(2) reserves to public bodies; the shipped path decides all 36 correctly and sends the cases where the keyword reader disagrees with the model to staff.

## What works and what does not

Works:
- All 10 sample requests end to end, in the terminal and in the web app.
- New requests typed into the form, including grouping by hospital and filtering stays by main diagnosis (tested against counts taken straight from the data).
- Opt-outs, the small-cell rule and the download block are enforced in code on the server, not in the browser.
- Staff see where the AI and the keyword reader disagree and can confirm or overrule with a reason.
- Staff see the three hospital databases with their patients, records and excluded opt-outs (totals only).
- If the LLM is down or rate limited, the app keeps working on the keyword reader and flags the case for staff review.

Does not, yet:
- Cases and staff actions live in memory; restarting the server clears them. No login.
- It runs locally; it is not deployed.
- The keyword fallback is much weaker than the LLM on unfamiliar wording.
- 4 red-team requests where the two AIs disagreed still wait for a human verdict (`redteam/REVIEW.md`).

## Repository

Start at `docs/MAP.md`. Rules for agents in `AGENTS.md`, for humans in `CONTRIBUTING.md`. Decisions in `docs/decisions/log.md`, handoffs in `docs/handoffs/`.

Synthetic data only. The challenge data under `challenge/` is the organisers' synthetic set, vendored byte for byte.
