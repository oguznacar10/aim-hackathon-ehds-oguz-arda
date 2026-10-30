# Decisions log

Append-only. Newest at the bottom. Every entry: date, title, who, PROPOSED or DECIDED, the why. A PROPOSED entry becomes DECIDED only through a later entry that says so.

## 2026-10-29 - Repo bootstrap (Arda, DECIDED)

- Private repo `arda03sarikaya-byte/aim-hackathon-ehds-oguz-arda`, becomes public at submission.
- `main` protected: PR required, `ci-green` required, squash merge, no force push.
- Agent rule set in `AGENTS.md` (all agents) with `CLAUDE.md` importing it; coding rules in `CODING_STANDARDS.md`.
- Challenge repo vendored byte for byte under `challenge/` (upstream commit ba0ff54) so CI and both teams' agents work offline.
- Stack: NOT decided. Brainstorm follows; the pick lands here as the next entry.

## 2026-10-30 - Decision engine: LLM reads, rules decide (Oguz via Devin, PROPOSED)

- Language: Python (matches the existing pytest/ruff CI). Code under `src/gatekeeper/`.
- The decision is never made by a model. An LLM answers only two questions about the request text: is the purpose prohibited under Art. 54 (and which point), and does the application explain why anonymised statistics are not enough (Art. 66(3)). Fixed code then applies the brief's four steps and attaches the articles. Why: 10 labelled examples are far too few to train a decision model, the law is a fixed procedure, and the metrics demand 10/10 correct and identical results over 3 runs.
- A keyword reader runs as a second opinion. When it disagrees with the LLM, the LLM answer stands and the result is flagged `needs_staff_review` for the staff view. Without an API key the keyword reader decides alone (offline fallback, not good enough for unseen requests).
- Consistency: temperature 0 and a disk cache keyed by prompt version, provider, model and request text.
- Only applicant, requested_as, purpose and question go to the LLM; patient data never does.
- Red-team loop to harden the reader: an attacker LLM writes tricky requests with an intended decision, a judge LLM (ideally another provider) labels them independently. Agreements go to `redteam/tuning` (used to improve the prompt) or `redteam/holdout` (never used for tuning, the honest score); disagreements go to `redteam/disputed` for a human to settle.
- Open: which LLM provider(s) and keys; stack for data, SPE and UI is a separate decision.

## 2026-10-30 - Statistics and SPE: SQLite, query plans, one small-cell function (Oguz via Devin, PROPOSED)

- Data: the five CSVs load into an in-memory SQLite database (Python standard library, no new dependency). Opted-out patients and all their rows are dropped while loading, so no query or SPE copy can reach them. Ages use 2025 minus birth year, as `challenge/data/README.md` says.
- Queries are never written per request. A planner turns the definitions into a JSON query plan (population filters, groups, count/percent/mean measures); `src/gatekeeper/query.py` validates every field (codes must look like codes, no free SQL) and compiles it to parameterised SQL. Staff see the plan and the SQL.
- Two planners write the same plan: a rule planner for the definition style of the 10 requests, and an LLM planner that sees only question, definitions and the code vocabulary (codes and labels, no patient rows). With a key the LLM plan is used and the rule plan runs as a second opinion; different numbers set `needs_staff_review`.
- Interpretations: a percent's denominator is the population of its group unless the definitions say otherwise; a mean counts the patients who have the value, and is suppressed below 10 of them; for counted stays, "by hospital" is the encounter's `data_holder`; patients outside every requested age band are left out.
- Every statistical value leaves through `smallcell.format_value` (counts below 10 as `<10`, percent and mean `suppressed`, halves rounded up with `Decimal`). Every requested group appears, even when empty.
- SPE: one SQLite file per approved application under `spe/<request id>/` (gitignored), with a `cohort` table and only the record types the question names (observations limited to the named LOINC codes), patient IDs kept. `spe.download()` always refuses and writes `audit.log` (Art. 73(2)).
- Open: the UI and the API on top of `pipeline.handle()`.

## 2026-10-30 - LLM via OpenRouter, gpt-4o as default, tests stay offline (Oguz via Devin, PROPOSED)

- Our key is an OpenRouter key, so `llm.py` has an `openrouter` provider (`OPENROUTER_API_KEY`, OpenAI-style endpoint). One key reaches several model families, so the red-team attacker and judge can come from different vendors: `--attacker-model openai/gpt-4o --judge-model anthropic/claude-haiku-4.5`.
- Default model on OpenRouter is `openai/gpt-4o`. On the 5 statistical requests plus R05, gpt-4o-mini planned 2/6 right and gpt-4.1-mini 4/6 (the others had wrong numbers or invalid plans); gpt-4o planned 6/6 (measured by comparing each LLM plan's numbers with the rule plan's).
- An LLM plan the validator rejects goes back to the LLM once, together with the validator error; if it still fails, the rule plan is used and staff review is flagged.
- The reader only flags a disagreement on `justifies_records` when it can change the outcome: an access application whose purpose is not prohibited.
- `tests/conftest.py` removes every LLM key from the test environment, so `pytest` never calls a paid API and never depends on a model.

## 2026-10-30 - Applicants no longer choose statistics or records - PROPOSED
Oguz asked that the system, not the researcher, decides between anonymised statistics and pseudonymised records. The web form no longer shows the "requested form" choice. A loaded sample request keeps the form from its JSON file, so R01-R10 still get the exact articles the brief expects. A new request typed into the form is sent as a health data access application, so rule 3 or 4 decides: records in an SPE only if the text explains why statistics are not enough, otherwise statistics.

## 2026-10-30 - Federated: one database per hospital, totals added centrally (Oguz via Devin, PROPOSED)

- `data.py` loads one in-memory SQLite database per data holder (Klinikum Nord, Süd, West), each with only that hospital's patients and their records. Every encounter in the data belongs to its patient's hospital, so the split is clean. Opted-out patients are still dropped while loading.
- A query plan runs in each hospital database. Only raw totals come back (counts, numerator/denominator, value sum and n for means); the access body adds them up and applies the small-cell rule once, on the totals. Suppressing per hospital first would hide counts that are safe in total.
- The SPE collects the cohort and its records from every hospital into one workspace; the manifest shows how many patients came from each.
- `data.connection()` (all hospitals in one database) stays only so tests can check that federated answers equal central ones.
- Verified: all five metrics unchanged (10/10, 6/6, 0 leaks, 10/10), with and without the LLM.
