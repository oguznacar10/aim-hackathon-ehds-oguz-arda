# Handoff: rule planner fails closed - 2026-10-30

## What changed
- `planner.rule_statistics_plan` refuses a measure phrase containing words that are neither a defined term nor in `planner.FILLER`.
- New test `test_rule_planner_refuses_a_measure_no_definition_explains`.
- Decision log entry PROPOSED.

## Verified
- `pytest -q`: 166 passed. `ruff check .`: clean.
- `scripts/eval_metrics.py --runs 3` without an LLM key: 10/10 decisions, 6/6 numbers, 0 leaks, 10/10 consistent.
- Web API: the type 2 diabetes request without a definition now returns HTTP 422 with the refusal reason instead of wrong counts.

## Open
- Not run with an LLM key in this session (no key in the environment).
- A new filler word an applicant uses (for example "currently") makes the fallback refuse. Add it to `FILLER` if it is harmless.

## Next step
- Review and merge the PR.
