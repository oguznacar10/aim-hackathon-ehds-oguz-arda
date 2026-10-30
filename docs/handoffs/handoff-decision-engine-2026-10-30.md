# Handoff - decision engine (2026-10-30, Oguz via Devin)

## What changed
- `src/gatekeeper/rules.py`: request validation and the four decision steps with articles and reason text.
- `src/gatekeeper/reader.py`: LLM reading (OpenAI or Anthropic, cached) plus keyword second opinion; disagreement sets `needs_staff_review`.
- `src/gatekeeper/llm.py`: minimal JSON client over urllib, no new dependency.
- `src/gatekeeper/redteam.py`: attacker/judge loop writing to `redteam/{tuning,holdout,disputed}`.
- `scripts/eval_decisions.py`: scores the 10 requests (or a red-team set) over 3 runs with timing.
- `tests/test_decision_rules.py`: the 10 requests as regression tests plus rule and validation tests.
- Proposal logged in `docs/decisions/log.md` (PROPOSED, needs Arda or Oguz to mark DECIDED).

## Verified
- `ruff check .` clean, `pytest -q` 53 passed.
- `python scripts/eval_decisions.py` with keyword reader only: 10/10 correct, 10/10 consistent over 3 runs.

## Not verified
- LLM path and red-team loop: no API key yet, never run against a real provider.

## Open / next
- Get an API key, run the eval with the LLM reader, then `python -m gatekeeper.redteam` (from `src/`) to build the test sets.
- The keyword reader is tuned to the 10 requests and will misfire on new wording (e.g. a public insurer doing research hits "insurance").
- Not started: term mapping, query generation, small-cell statistics, SPE, UI.
