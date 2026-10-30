# Handoff - synthetic request generator (2026-10-30, Arda via Claude)

## What changed
- `src/gatekeeper/synth.py`: generator for labelled training requests. A slot generator builds the question and definitions from the real vocabulary (the 11 condition prefixes, matching ATC and LOINC codes in `PAIRS`, regions, encounter types, the 31 December 2025 date) in seven shapes copied from the originals (count, prevalence, mean, stays, active medication, treatment gap, two-drug percent) plus the R05 cohort shape. An LLM writes only `applicant` and `purpose`, steered by one of 11 targets (54(a) to 54(d) worded innocently, public and private statistics, a private applicant with a reserved 53(2) purpose, justified and public SPE, bare claim, no claim). Gate: `redteam.validate_generated()` then the rule planner run on the data (`synth.answer()`); a request the data cannot answer goes to `synth/invalid/`. Label: `rules.decide()` with the reading the target implies, stored as `expected` with decision, articles and reason. Optional judge (`redteam.judge`) routes disagreements to `synth/disputed/`; agreements split into `synth/tuning/` and `synth/holdout/` by the same hash rule as the red-team loop. The anonymised answer is stored too.
- `tests/test_synth.py`: codes in `PAIRS` exist in the data; every shape passes the validator and runs on the data; every target labels as intended through the rules, the 53(2) target with articles ["53"]; SPE targets never ask for a table; `generate()` is deterministic per seed and writes labelled files; judge disagreement lands in disputed; the writer prompt carries no patient rows.
- `docs/MAP.md`: one line for the generator.

## Verified
- `python3 -m pytest -q`: 183 passed (on main after PR 15).
- `uvx ruff==0.17.0 check .`: clean.
- `scripts/em-dash-guard.sh origin/main`: clean.
- No LLM was called. No generation run was made. `--n` and `--seed` are required arguments with no defaults.

## Not verified
- The LLM writer end to end (prompt quality of purpose and applicant text). First run is Arda's, with his number.
- Target mix: uniform over the 11 targets gives roughly 5 REJECT : 2 statistics request : 2 SPE : 2 application downgraded. Change the draw in `generate()` if the training set needs another balance.

## Open / next
- Arda gives N and the seed; run `python -m gatekeeper.synth --n N --seed S --judge <other provider>` with the key fetched by the runtime (Secret Manager path in `llm.py`).
- Human tick of `synth/holdout/` and `synth/disputed/` before any training (`scripts/redteam_review.py` reads `redteam/` only; point it at `synth/` or copy the pattern).
- Whether a trained model may decide is still an open log entry; this generator only produces data.

## Review fixes (same day, PR after the blind review)
- The judge sees only the request fields (`synth.judge_input()` strips expected, target, answer); a test records what the judge receives.
- `redteam.JUDGE_PROMPT` now carries the decided Art. 53(2) rule and the Art. 66(3) second limb, so the red-team loop and the generator judge with the same five rules.
- `generate()` takes `max_attempts` (CLI `--max-attempts`, required, no default): it bounds writer calls, so a failing writer cannot spend without limit. Writer and judge errors (bad JSON, HTTP after retries) are counted as malformed or recorded in the file instead of aborting the run.
- The gate drops a request whose every cell is `<10` or `suppressed` (2 of 155 distinct shapes over 600 seeds in the review sweep).
- `answer()` uses `rules.report_is_table()` and `pipeline._cohort_size()`; example prompts are read once; the `submitted` offset is +02:00 before 25 October 2026.
- Verified: `python3 -m pytest -q` 192 passed, `uvx ruff==0.17.0 check .` clean, em-dash guard clean. Still no LLM call and no generation run.
