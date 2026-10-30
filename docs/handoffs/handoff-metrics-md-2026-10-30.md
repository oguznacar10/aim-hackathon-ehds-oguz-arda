# Handoff: METRICS.md - 2026-10-30

## What changed
- New `METRICS.md` at the repo root: the five challenge metrics, offline and with the key, a per-request table, how each metric is measured, limits, and how to reproduce. Linked from the README metric section and from `docs/MAP.md`.

## Verified
- `PYTHONPATH=src python scripts/eval_metrics.py` on `main` at `9fd29f9`, no key: 10/10 decisions, 6/6 numbers, 0 leaks, 10/10 consistent, slowest 0.75 s. The per-request table is copied from that output.

## Open
- unverified: the run with `OPENROUTER_API_KEY` on the current code. The key column carries the earlier run, made before PRs #13 and #21. Re-run with a key and update both `METRICS.md` and the README table.

## Next step
- Merge after Oguz or Arda says so.
