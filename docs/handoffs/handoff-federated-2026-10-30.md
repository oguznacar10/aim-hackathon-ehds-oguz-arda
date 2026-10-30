# Handoff: federated hospital databases (2026-10-30)

## What changed
- `data.nodes()`: one in-memory SQLite database per hospital (data holder). Queries and SPE copies run per hospital; only totals come back to the access body, which adds them up and applies the small-cell rule once.
- Staff case file says how many hospital databases answered.
- `tests/test_federated.py`: each hospital holds only its own patients, federated answers equal the central answer for R01, R03, R07, R08, R09, and the R05 SPE cohort (1,152) is the sum over the hospitals.

## Verified
- `pytest -q`: 118 passed; `ruff check .`: clean
- `python scripts/eval_metrics.py` offline: 10/10, 6/6, 0 leaks, 10/10, slowest 0.74 s
- Same with `OPENROUTER_API_KEY`: 10/10, 6/6, 0 leaks, 10/10, slowest 0.97 s (LLM answers cached)

## Open
- README "Federated or central" paragraph to update once the README PR is merged.
- The hospital databases still live in one process; a real deployment would put each behind its own service.
