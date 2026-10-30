# Handoff: code for the Art. 66(3) and Art. 53(2) rules (2026-10-30, Arda's session)

Implements the 2026-10-30 log entry "Art. 66(3) justification threshold and Art. 53(2) private applicants (Arda, DECIDED)".

## What changed
- `src/gatekeeper/reader.py`: two new facts from both readers, `public_body` and `reserved_purpose_only`; the LLM prompt no longer says public purposes are allowed "even by companies" and now states Art. 53(2); `justifies_records` needs a named mechanism (train, validate, link, follow over time, compare individual responses), a bare "essential" is a claim; `PROMPT_VERSION` is "2", so LLM reading caches reset.
- `src/gatekeeper/rules.py`: `blocked_by_53_2()` gives REJECT with articles `["53"]`, rule 1, `needs_staff_review` always on; `report_is_table()` sends a justified application whose Report line is counts, percentages or means per group to rule 4 (53, 66, 69) with a reason naming Art. 66(2).
- `src/gatekeeper/static/app.js`: step 1 label and two more rows in the staff "who read the request" table.
- `tests/test_decision_rules.py`: private insurer claiming official statistics is refused under 53; the statistics office keeps it; a private applicant whose purpose also fits research is approved; reader disagreement on 53(2) flags review; justified records plus a table fall to rule 4; a bare assertion is no justification; R05's Report line is not a table.

## Verified
- `ruff check .` clean, `pytest -q` 172 passed (offline, keyword reader).
- `python scripts/eval_metrics.py` offline: see the PR description for the printed lines.

## Not verified
- The LLM reader on the new prompt: no key in a session. Arda runs `scripts/eval_metrics.py` and `scripts/eval_decisions.py --mode hybrid --no-cache` from his terminal; the cache is empty for prompt version 2, so every reading is fresh.
- `decision.py` (Nimble, Jev) does not ask the 53(2) questions; those ablation modes never produce the 53(2) refusal.

## Open
- The 10 samples contain no 53(2) case, so the live reader's behaviour on one is unmeasured until the synthetic set exists.
