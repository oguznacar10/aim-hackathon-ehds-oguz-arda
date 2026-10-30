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

## With the real LLM (OpenRouter key, `OPENROUTER_API_KEY`, reader and planner `openai/gpt-4o`)
- `python scripts/eval_metrics.py`: correct decisions 10/10, correct numbers 6/6 (every plan from the LLM, none fell back to rules), privacy leaks 0, consistent over 3 runs 10/10 (runs 2 and 3 come from the cache), slowest answer 1.70 s.
- Red team, attacker `openai/gpt-4o`, judge `anthropic/claude-haiku-4.5`, 12 requests: 8 agreed (all in `redteam/tuning/`), 4 disputed. `python scripts/eval_decisions.py --set tuning`: 8/8 correct, 8/8 consistent.
- A first batch with looser prompts was discarded: the attacker rejected legitimate research for made-up reasons and the judge granted SPE without a justification. One of its "agreed" cases had a wrong label, which is why agreed cases still need a human look.

## Not verified
- The labels in `redteam/` are LLM labels, not reviewed by Oguz or Arda yet.
- Rule planner on wording far from the challenge style; that is what the LLM planner is for.

## Next
- Oguz or Arda settle the 4 files in `redteam/disputed/` and spot-check `redteam/tuning/`.
- Generate more red-team batches with different `--focus` values; keep `redteam/holdout/` untouched for the final score.
- UI / API for applicants and staff on top of `pipeline.handle()`, including a blocked-download demo.
- README: run instructions and architecture.
