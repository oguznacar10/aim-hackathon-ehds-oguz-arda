# Metric results on the 10 requests

The five metrics from `challenge/README.md`, measured with `scripts/eval_metrics.py` on the 10 requests in `challenge/requests/` against `challenge/requests/expected.json`.

## Summary

| Metric | Target | Offline (no key) | With `OPENROUTER_API_KEY` |
|---|---|---|---|
| Correct decisions | 10 of 10 | 10 of 10 | 10 of 10 |
| Correct numbers | 6 of 6 | 6 of 6 | 6 of 6 |
| Privacy leaks | 0 | 0 | 0 |
| Consistency over 3 runs | 10 of 10 | 10 of 10 | 10 of 10 |
| Slowest request | under 60 s | 0.75 s | 12.7 s |

- **Offline:** run on 30 October 2026 on `main` at commit `9fd29f9`, `runs=3 reader=keywords`. A keyword reader and the rule planner replace the LLM.
- **With the key:** run on 30 October 2026 with the LLM cache emptied first, so the first of the 3 runs made real LLM calls (reader and planner `openai/gpt-4o`, temperature 0). This run was made before the planner changes in PRs #13 and #21 and has not been repeated since.

## Per request (offline run)

| Request | Decision | Articles | Decision correct | Numbers correct | Planner | Leaks |
|---|---|---|---|---|---|---|
| R01 | APPROVE_STATISTICAL | 53, 69 | yes | yes | rules | 0 |
| R02 | REJECT | 54 | yes | - | - | 0 |
| R03 | APPROVE_STATISTICAL | 53, 69 | yes | yes | rules | 0 |
| R04 | REJECT | 54 | yes | - | - | 0 |
| R05 | APPROVE_SPE | 53, 66, 68, 73 | yes | yes | rules | 0 |
| R06 | REJECT | 54 | yes | - | - | 0 |
| R07 | APPROVE_STATISTICAL | 53, 69 | yes | yes | rules | 0 |
| R08 | APPROVE_STATISTICAL | 53, 69 | yes | yes | rules | 0 |
| R09 | APPROVE_STATISTICAL | 53, 66, 69 | yes | yes | rules | 0 |
| R10 | REJECT | 54 | yes | - | - | 0 |

"-" under numbers: a rejected request has no numbers to check. For R05 (SPE) the checked number is the exact patient count copied into the secure processing environment.

## How each metric is measured

- **Correct decisions:** decision and articles equal `expected.json`; adding Art. 67 or 71 is allowed.
- **Correct numbers:** every expected value appears under its group in our answer.
- **Privacy leaks:** a statistical answer that contains a patient-level record, a count below 10, an unsuppressed percentage or mean, or an opted-out patient.
- **Consistency:** the same decision, articles and answer in all 3 runs.
- **Slowest request:** the longest single `pipeline.handle()` call over all runs, from request in to answer out. The first call also loads the data.

## Limits

- With the key, runs 2 and 3 reuse the cached LLM answers, so consistency is partly guaranteed by the cache.
- The 10 requests are the only labelled set from the organisers. Scoring 10 of 10 does not show how the app does on new wording. Offline, the rule planner refuses a request whose measure no definition explains, instead of guessing numbers.

## Reproduce

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\eval_metrics.py
```

Set `$env:OPENROUTER_API_KEY` first for the run with the LLM. The first output line shows which reader ran (`reader=keywords` means offline).
