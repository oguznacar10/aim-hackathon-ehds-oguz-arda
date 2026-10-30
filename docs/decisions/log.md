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
