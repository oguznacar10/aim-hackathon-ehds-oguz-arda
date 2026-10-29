# Agent rules - aim-hackathon-ehds-oguz-arda

Read this whole file before touching anything. It applies to every coding agent (Claude Code, Codex, IBM Bob, Cursor, Devin) and to both humans, Arda and Oguz.

## What this repo is

A Health Data Access Body app for the AIM Healthcare Hackathon Vienna 2026, Track 3 (European Health Data Space). It takes a request as JSON, decides REJECT / APPROVE_STATISTICAL / APPROVE_SPE with article citations, computes anonymised statistics under the small-cell rule, or copies pseudonymised records into a secure processing environment with downloads blocked. The spec is `challenge/README.md`. The law and the hackathon facts are under `docs/challenge/`. Start at `docs/MAP.md`.

Deadline: Friday 30 October 2026, 15:00 (submission form). Team: Oguz Nacar and Arda Sarikaya.

## How to work here

1. **Read before you write.** `docs/MAP.md`, then the newest file in `docs/handoffs/`, then `docs/decisions/log.md` from the bottom. Never redo a decision that is logged; propose a change as a new entry instead.
2. **Small PRs, one topic each.** Branch from `main`, name it `<who>/<topic>` (for example `arda/decision-engine`, `oguz/spe-copy`). Open a PR early, even as draft.
3. **CI green before merge. No exceptions.** The `ci-green` check is required on `main`. A red check is fixed, never bypassed, never force-pushed around.
4. **Verify before you claim.** "Done" means you ran the thing and saw the output. Paste the command and the result in the PR, or say "unverified: <reason>". A metric number in a PR or README comes from a run, never from memory.
5. **No fabricated metrics anywhere.** The submission asks for our results on the 10 requests. Report what the app actually produced, including failures. The video has to say what works and what does not.
6. **Hand off in writing.** When you stop, append `docs/handoffs/handoff-<topic>-<date>.md`: what changed, what is verified, what is open, the next step. The other person's agents start from that file.
7. **Log decisions.** Any choice the other person would need to know (stack, schema, output format, how a rule is interpreted) goes to `docs/decisions/log.md` with the date, the why, and PROPOSED or DECIDED. A proposal becomes DECIDED only when Arda or Oguz says so in the log.
8. **Delegate, do not type.** An orchestrating agent plans and reviews; workers implement and run tests. Never read a large file whole into an expensive context when a worker can summarise it.
9. **Ask when the readings diverge.** If the spec allows two materially different builds, write both in one short message and let a human pick. Routine calls you make yourself.

## Hard rules (never cross)

- **Synthetic data only.** Everything under `challenge/data/` is synthetic. No real patient data enters this repo, ever, in any form.
- **Patient-level data stays inside the app.** Request text may go to a cloud LLM; rows from `challenge/data/` never do. No patient rows in logs, PR descriptions, screenshots, or chat.
- **Opted-out patients are excluded from every count, every denominator, and every SPE copy.**
- **Small-cell rule is total:** counts below 10 (including 0) show `<10`; a percentage with numerator or denominator below 10 and a mean of fewer than 10 patients show `suppressed`; every requested group appears, even when empty; round to one decimal, halves up.
- **Articles list = exactly the set the brief gives, plus at most Art. 67 or 71.** Art. 61 and 68(3) are correct law but go in the reason text only. Detail in `docs/challenge/README.md`.
- **No secrets in tracked files.** Keys live in local env files that `.gitignore` covers. gitleaks runs on every push over full history.
- **Hyphen, never the em-dash,** in anything we ship: code, docs, README, video script, PR text. CI checks added lines.
- **No recursive deletes, no hard resets of git history, no force pushes to shared branches.** Move a branch with `git branch -f` or a fast-forward merge.
- **Pinned installs.** Exact versions for packages, checksums for downloaded binaries, major tags for GitHub Actions, no piping a download into a shell.
- **Comments state only a constraint the code cannot show.**
- **Do not edit `challenge/`.** It is the organisers' repo copied byte for byte. Re-copy from upstream if it changes.

## Return format for workers

A worker agent returns at most 10 lines: files changed (paths only), what was verified and how (command + pass/fail counts), open risks. No code, no logs, no diffs. A failing test is named with a one-line cause.

## Where things are

See `docs/MAP.md`. If it is wrong, fix it in the same PR that made it wrong.
