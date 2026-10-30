# Map

Where everything is. Read top to bottom once, then jump.

| You need | Open |
|---|---|
| The rules for working here | `AGENTS.md` (agents) and `CONTRIBUTING.md` (humans and PR flow) |
| What to build, decision order, small-cell rule, metrics, judging | `challenge/README.md` |
| Data dictionary (columns, 31 Dec 2025 reference date, LOINC codes, opt-out flag) | `challenge/data/README.md` |
| The 10 test requests and the answer key | `challenge/requests/R01.json` to `R10.json`, `challenge/requests/expected.json` |
| The synthetic data (20,000 patients, 5 CSVs) | `challenge/data/*.csv` |
| What an EHDS article actually says, verbatim | `docs/challenge/ehds-articles/art-<N>.md` (53, 54, 61, 66, 67, 68, 69, 71, 73) |
| Which article backs which decision, what the brief leaves implicit, hard rules for the build | `docs/challenge/README.md` |
| Team, deadline, submission form, jury, tools and credits (Exoscale, Devin, Lovable, Bob) | `docs/challenge/hackathon-notes.md` |
| What has been decided (stack, schema, interpretations) | `docs/decisions/log.md`, read from the bottom |
| Where the last session stopped | newest file in `docs/handoffs/` |
| Implementation plans | `docs/plans/` |
| Coding rules CI enforces or a reviewer judges | `CODING_STANDARDS.md` |
| CI definition | `.github/workflows/ci.yml` |
| Em-dash guard used by CI | `scripts/em-dash-guard.sh` |
| Fixture sanity tests | `tests/` |
| Decision engine (LLM reading + rules), red-team loop | `src/gatekeeper/` (`reader.py`, `rules.py`, `redteam.py`) |
| One request end to end (decide, then statistics or SPE) | `src/gatekeeper/pipeline.py` |
| Data access without opted-out patients, query plans, small-cell rule, SPE | `src/gatekeeper/data.py`, `query.py`, `smallcell.py`, `spe.py` |
| Definitions to query plan (rules and LLM) | `src/gatekeeper/planner.py` |
| Decision scoring on the 10 requests or a red-team set | `scripts/eval_decisions.py` |
| All five challenge metrics on the 10 requests | `scripts/eval_metrics.py` |
| Web app: applicant notice, staff case file, blocked download (`python scripts/serve.py`) | `src/gatekeeper/web.py`, `src/gatekeeper/static/` |
| Red-team test sets (tuning, held-out exam, disputed) and the human review sheet | `redteam/`, `redteam/REVIEW.md` (rebuild with `scripts/redteam_review.py`) |

## Facts that must not drift

- Team: Oguz Nacar and Arda Sarikaya, two people.
- Deadline: Friday 30 October 2026, 15:00, one Google Form submission: video max 2 min, public repo with architecture README, metric results on the 10 requests.
- The repo goes public at submission. Nothing in it may be something we would not publish.
- Articles list tolerance: only Art. 67 or 71 may be added. Everything else is reason text.
