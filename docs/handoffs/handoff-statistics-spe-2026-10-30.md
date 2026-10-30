# Handoff - statistics and SPE (2026-10-30, Oguz via Devin)

Branch `oguz/statistics-spe`, stacked on `oguz/decision-engine` (PR #2).

## What changed
- `src/gatekeeper/data.py`: in-memory SQLite copy of the CSVs without opted-out patients; code vocabulary for the LLM.
- `src/gatekeeper/query.py`: JSON query plan language, validation, compilation to parameterised SQL, execution.
- `src/gatekeeper/smallcell.py`: the one small-cell function every statistical value goes through.
- `src/gatekeeper/planner.py`: rule planner (definitions to plan or SPE spec) and LLM planner (request text and code vocabulary only).
- `src/gatekeeper/spe.py`: per-application SQLite workspace under `spe/`, download always blocked and audited.
- `src/gatekeeper/pipeline.py`: `handle(request)` = read, decide, then statistics or SPE, with a staff section (plan, SQL, planner, review note).
- `scripts/eval_metrics.py`: the five challenge metrics; `tests/test_statistics_spe.py`.

## Verified
- `ruff check .` clean, `pytest -q` 76 passed.
- `python scripts/eval_metrics.py` (keyword reader, rule planner, no API key): correct decisions 10/10, correct numbers 6/6, privacy leaks 0, consistent over 3 runs 10/10, slowest answer 0.45 s.
- Two unseen-style requests (stays by main diagnosis per hospital; patients by hospital) match an independent count straight from the CSVs.

## Not verified
- LLM planner: no API key yet. Its prompt and validation exist; it has never run.
- Rule planner on wording far from the challenge style; that is what the LLM planner is for.

## Next
- Add an API key, run `python scripts/eval_metrics.py`, compare LLM and rule plans, fix the prompt.
- UI / API for applicants and staff on top of `pipeline.handle()`, including a blocked-download demo.
- README: run instructions and architecture.
