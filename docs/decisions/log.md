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

## 2026-10-30 - Generated requests must pass a data-dictionary validator before they count (Arda, PROPOSED)

- Review of the 12 red-team requests on `oguz/statistics-spe` (file `redteam/REVIEW.md`): JSON shape right, labels mostly defensible, content unrealistic. Two of the last two cite codes that do not exist in `challenge/data` (ICD-10 G89; "LOINC codes related to nutritional products" when the data has four LOINC codes), both have two vague definitions where the originals have four to six, and `requested_format` uses free wording. The judge also rejected two requests for who the applicant is, which the brief does not allow.
- Change: the attacker prompt now receives the real vocabulary read from the CSVs (13 ICD-10, 16 ATC, 4 LOINC codes with names, 9 regions, 3 hospitals, the 31 December 2025 reference date), two examples (R03 statistics, R05 records) instead of one, and explicit realism rules. Every generated request goes through `redteam.validate_generated()` before the judge sees it; failures land in `redteam/invalid/` with the reasons. The validator accepts all 10 originals and rejects `Gde652cfe`.
- Why: a training set or a live demo built on requests the data cannot answer would embarrass us in front of the access-body jurors, and free `requested_format` wording would teach a classifier a spurious signal.
- Still a human call: the Art. 66(3) borderline (one-sentence "individual-level data is crucial" justifications). The same judge accepted it in `Gde652cfe` and refused the same pattern in `Ga9a3dfc0`; settle the rule once in this log before generating more.
- Open: whether a trained model may decide at all. The 2026-10-30 "LLM reads, rules decide" entry says no; Arda's plan to train on generated requests needs its own entry (model as second opinion versus model as decider).


## 2026-10-30 - An LLM outage never stops a request (Oguz via Devin, PROPOSED)

- A fresh run without the cache hit HTTP 429 from OpenRouter and crashed the pipeline. Now `llm.chat_json` retries 429 and 5xx up to 3 times (1 s, 2 s, 4 s), and if the reader still gets no answer the keyword reader decides and the case is flagged `needs_staff_review` with the error text. The planner already fell back to the rule plan.


## 2026-10-30 - Federated: one database per hospital, totals added centrally (Oguz via Devin, PROPOSED)

- `data.py` loads one in-memory SQLite database per data holder (Klinikum Nord, Süd, West), each with only that hospital's patients and their records. Every encounter in the data belongs to its patient's hospital, so the split is clean. Opted-out patients are still dropped while loading.
- A query plan runs in each hospital database. Only raw totals come back (counts, numerator/denominator, value sum and n for means); the access body adds them up and applies the small-cell rule once, on the totals. Suppressing per hospital first would hide counts that are safe in total.
- The SPE collects the cohort and its records from every hospital into one workspace; the manifest shows how many patients came from each.
- `data.connection()` (all hospitals in one database) stays only so tests can check that federated answers equal central ones.
- Verified: all five metrics unchanged (10/10, 6/6, 0 leaks, 10/10), with and without the LLM.

## 2026-10-30 - Decision models supply the two facts, rules still decide; LLM-alone is ablation only (Arda, PROPOSED)

- The shipped path is unchanged: `pipeline.handle()` calls `reader.read()` then `rules.decide()`. No model decides in the app.
- PR #5 adds readers that answer the same two facts (Art. 54 purpose, Art. 66(3) justification) from a decision model instead of an LLM prompt: `src/gatekeeper/decision.py` speaks one typed-question contract to Nimble (Bespoke Labs 9B, local through Ollama, no key) and Jev (TypeSafe, hosted, key). The rules in `rules.py` still make the decision. Only applicant, requested_as, purpose and question are sent.
- `src/gatekeeper/direct.py` lets an LLM decide end to end. It is imported only by `scripts/eval_decisions.py` and its tests, never by the pipeline or the web app. It exists so the eval can put "LLM alone", "rules alone" and "LLM reads, rules decide" on the same requests.
- Eval modes: rules (keywords + rules), hybrid (LLM reads, rules decide, the shipped path), llm (ablation only), nimble and jev (decision model reads, rules decide), vote (LLM reads, Nimble as second opinion, disagreement escalates to staff). Errors are split into dangerous (more data than the law allows) and restrictive (less), with unflagged dangerous errors, escalations and latency p95 reported.
- Why: the 2026-10-30 "LLM reads, rules decide" entry stands. This entry records that a decision model is allowed in the reader seat, which that entry did not cover, and that a model in the decider seat is for measurement only. A trained model as decider needs its own entry, which is not proposed here.
- Open: live numbers for every mode except rules. Those runs start from Arda's terminal; see PR #5.

## 2026-10-30 - Art. 66(3) justification threshold and Art. 53(2) private applicants (Arda, DECIDED)

Arda approved both readings in his session on 2026-10-30 after the review of the 12 red-team requests (`redteam/REVIEW.md`), where the judge LLM accepted a one-sentence justification in `Gde652cfe` and refused the same pattern in `Ga9a3dfc0`, and rejected `Gc3b2cb72` for the applicant's identity. These rules bind `rules.py`, the reader prompts, the label step of any generated request, and human verdicts in `redteam/REVIEW.md`.

- **Art. 66(3), when an access application earns pseudonymised records (rule 3 of the brief).** Both must hold. (1) The text names what will be done with individual records that anonymised statistics cannot do: train or validate a model on patient histories, link records to another dataset, follow patients over time, or compare responses between individual patients. "Essential", "crucial" or "we need individual data" alone is a claim, not a justification. (2) What the request asks to report is not itself counts, percentages or means per group; if the "Report" definition is a table, statistics answer the question and rule 4 applies with Art. 53, 66, 69, as in R09. Under this rule R05 passes and R09 fails; `Gde652cfe` passes on (1) narrowly, `Ga9a3dfc0` fails.
- **Art. 53(2), a private applicant claiming a purpose reserved for public bodies.** If the stated purpose fits only public health, policy-making or official statistics (Art. 53(1)(a), (b), (c)), the applicant has no allowed purpose: REJECT, articles `["53"]`, reason quoting Art. 53(2), flagged `needs_staff_review` because an access body would ask for a reframed application. If the purpose also fits scientific research (e) or improving care (f), approve under that point and say in the reason that the public-health framing does not apply to a private body. `Gc3b2cb72` (insurer, "improve public health strategies", statistics) is REJECT under 53, not 54. Known risk, accepted by Arda: every REJECT in `expected.json` cites Art. 54 alone, so a hidden jury case of this type may score the article list differently; the 10 samples contain no such case.
- **Generated requests for training (approved in principle, run size still Arda's).** Definitions and question are built from the real vocabulary (13 ICD-10, 16 ATC, 4 LOINC codes, 9 regions, 3 hospitals, 31 December 2025); an LLM writes only purpose and applicant toward a target category; every request passes `redteam.validate_generated()` and is executed by the planner on the data, and one that yields no result table is dropped; labels (decision, articles, reason) come from `rules.py`, the judge LLM only routes disagreements to a human. The 12 files under `redteam/` fail the validator (12 of 12, run 2026-10-30) and seed nothing.
- **Model role.** Unchanged from the 2026-10-30 "Decision models supply the two facts" entry: a model reads and may propose a decision, rules decide and cite, disagreement escalates to staff. A trained model in the decider seat still needs its own entry.

## 2026-10-30 - The rule planner refuses a measure it cannot fully explain (Oguz via Devin, PROPOSED)

- Without an LLM, the request "Report per hospital: patients with type 2 diabetes." (no definition for type 2 diabetes) returned every patient per hospital. The rule planner ignored words it did not know and counted the whole population.
- Now every measure in the "Report per ...:" line may only use defined terms plus filler words (with, patients, how many, share, %, ...). Any other word stops planning with "'<measure>' uses words no definition explains: ...". The web app shows that as "the numbers could not be planned". With an LLM key the LLM plan is still tried first; this only changes the fallback.
- Why: a wrong number is worse than no number for an access body. All 10 sample requests still plan the same (10/10, 6/6 offline).

## 2026-10-30 - Live ablation on the 10 requests: every mode 10/10, the 10 cannot rank readers (Arda, PROPOSED)

- Run today on commit `573297a`, `--runs 3 --no-cache`: rules, hybrid (gpt-4o reads), llm (gpt-4o decides, ablation only), nimble (local, no key), vote. All five: 10/10 correct, 10/10 consistent, 0 dangerous, 0 unflagged, 0 escalated. p95: rules 0.00 s, nimble 1.10 s, vote 1.48 s, llm 1.92 s, hybrid 2.21 s. Full output in `docs/handoffs/handoff-decision-ablation-2026-10-30.md`. jev not run.
- What we may claim: the shipped path (hybrid) and the local Nimble reader both score 10/10 live on the challenge set; the local reader needs no key and no cloud call. What we may not claim: that any mode is safer than another; 30 decisions with 0 failures bound the true failure rate only to 10%.
- Why PROPOSED: the ranking question stays open until the synthetic held-out set exists (PR 16) and the modes run on it at Arda's batch size. The shipped path does not change on these numbers.

## 2026-10-30 - Product name .Gatekeeper (Oguz via Devin, PROPOSED)

The app is called Gatekeeper, shown as the wordmark ".Gatekeeper" in the header, the tab title, the server banner and the README intro, replacing Datenzugang (PR 17). Becomes DECIDED when Arda or Oguz says so here.

## 2026-10-30 - Art. 53(2) third-party clause: a private contractor working for a public body (Arda via Claude, PROPOSED)

- Art. 53(2) reserves the purposes in Art. 53(1)(a), (b), (c) to public bodies "including where processing of data for carrying out those tasks is done by a third party on behalf of those public sector bodies". The decided 2026-10-30 entry on 53(2), `rules.py` and `redteam.JUDGE_PROMPT` all treat every private applicant with such a purpose as REJECT [53] and do not read the clause.
- Found by the blind review of synth run 1: 4 of 40 generated requests are a private consultancy or wholesaler preparing planning input "under a contract with a federal state" or "for a regional health authority". Under the clause an access body would ask for the mandate and could approve under Art. 53(1)(a) or (b) as statistics; under the current rules it rejects.
- Proposed reading: a private applicant who states that it processes on behalf of a named public body for that body's task is treated as the public body for Art. 53(2), flagged `needs_staff_review` so staff verify the mandate; a private applicant claiming the purpose for itself stays REJECT [53]. Until decided, the 4 files sit in `synth/disputed/` and seed nothing. If decided, `rules.py`, the judge prompt and the `private_reserved_purpose` writer brief ("the applicant claims the purpose for itself, not on behalf of a public body") change together.

## 2026-10-30 - Synthetic set ranks the readers: hybrid and vote 36/36, model alone 33/36 (Arda via Claude, PROPOSED)

- The 2026-10-30 "Live ablation" entry left the ranking open until a synthetic held-out set existed. Run today on `synth/tuning` (25) and `synth/holdout` (11), 3 runs, no cache, gpt-4o through OpenRouter: rules 14 and 4, nimble 22 and 9, llm alone 23 and 10 (9 dangerous decisions of 108, none flagged), hybrid and vote 25 and 11 with 0 errors and 58 of 108 decisions escalated to staff. Every mode was consistent over the 3 runs.
- What we may claim: on requests the keyword reader cannot handle, the shipped path (model reads, rules decide) makes no error, and the model alone grants records it should not. The escalation rate is the price and is honest: the keyword second opinion disagrees exactly on the disguised purposes.
- Why PROPOSED: 36 requests, 11 targets with 2 to 5 each; a second seed with Arda's numbers is needed before the ranking counts as settled. The 4 disputed 53(2) files are excluded.
