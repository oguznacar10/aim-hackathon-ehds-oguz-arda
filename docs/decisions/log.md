# Decisions log

Append-only. Newest at the bottom. Every entry: date, title, who, PROPOSED or DECIDED, the why. A PROPOSED entry becomes DECIDED only through a later entry that says so.

## 2026-10-29 - Repo bootstrap (Arda, DECIDED)

- Private repo `arda03sarikaya-byte/aim-hackathon-ehds-oguz-arda`, becomes public at submission.
- `main` protected: PR required, `ci-green` required, squash merge, no force push.
- Agent rule set in `AGENTS.md` (all agents) with `CLAUDE.md` importing it; coding rules in `CODING_STANDARDS.md`.
- Challenge repo vendored byte for byte under `challenge/` (upstream commit ba0ff54) so CI and both teams' agents work offline.
- Stack: NOT decided. Brainstorm follows; the pick lands here as the next entry.
