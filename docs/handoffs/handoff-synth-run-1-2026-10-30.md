# Handoff - synthetic request run 1 (2026-10-30, Arda via Claude)

## What changed
- `synth/tuning/` (29 files) and `synth/holdout/` (11 files): the first batch of labelled synthetic requests. `synth/disputed/` is empty. Run: N 40, seed 1, max-attempts 60; the first 40 prompts were used, 20 were never written.
- `scripts/synth_agents.py`: drives `gatekeeper.synth` in three phases (`draw`, `assemble`, `route`) with Claude Code agents as writer and judge instead of API calls. Writers were two Opus 5.5 agents (30 prompts each), judges two Fable 5.1 agents (20 requests each). Writers saw only the writer prompt; judges saw only `redteam.JUDGE_PROMPT` with the request fields (`synth.judge_input`, no expected, target or answer).
- `scripts/eval_decisions.py`: `--set` takes a path such as `synth/tuning` and reads a dict `expected` as decision plus articles, so articles are scored on synthetic sets too.
- `docs/MAP.md`: one line for the driver.

## Run statistics (from the run, not from memory)
- assemble: kept 40, invalid 0, malformed 0, unwritten 0 (of 60 drawn, 40 used).
- route: tuning 29, holdout 11, disputed 0. The judges agreed with the rules label on all 40.
- Targets kept: reject_54c 5, spe_mechanism 5, private_reserved_purpose 5, reject_54b 5, reject_54d 4, reject_54a 4, spe_public 3, app_bare_claim 3, stat_research 2, app_no_claim 2, stat_public 2.
- Decisions kept: REJECT 23, APPROVE_STATISTICAL 9, APPROVE_SPE 8.

## Offline eval (3 runs each, no key)
- `--mode rules` (keyword reader + rules): tuning 15/29 correct, 29/29 consistent, 30 dangerous unflagged of 87; holdout 4/11, 11/11 consistent, 9 dangerous unflagged of 33. Misses by target: spe_mechanism 5, reject_54a 4, private_reserved_purpose 4, reject_54b 3, spe_public 3, reject_54c 2. The keyword reader cannot see an innocently worded prohibited purpose or a mechanism sentence; that is what the set is for.
- `--mode nimble` (Nimble reads through Ollama, rules decide): tuning 22/29 correct, 29/29 consistent, 21 dangerous unflagged of 87, 0 restrictive; holdout 9/11, 11/11 consistent, 3 dangerous unflagged of 33, 3 restrictive. Misses by target: private_reserved_purpose 5, reject_54b 2, reject_54a 1, spe_public 1. Latency p95 under 1 s (cache on after run 1).

## Hand read of 10 kept requests
- Purposes read like real applications and fit their question; unlawful targets are worded innocently (communication plans, consumer research, credit scoring) as the targets ask.
- SPE purposes name a concrete mechanism (sequence training, longitudinal linkage); the 53(2) insurer case claims a policy purpose plausibly.
- Weak spots: the spirits and e-cigarette cases tie the product to the health question loosely; one insurer purpose would pass as research if read generously.

## Not verified
- `--mode hybrid`, `--mode llm`, `--mode vote` need the OpenRouter key and are Arda's to run from his terminal:
  `OPENROUTER_API_KEY_SECRET=projects/project-beta-482921/secrets/openrouter PYTHONPATH=src python3 scripts/eval_decisions.py --set synth/tuning --mode hybrid --runs 3` (then `--mode llm`, `--mode vote`, and `--set synth/holdout`).
- No human tick of `synth/holdout/` yet. Judge agreement is not a human review.

## Open / next
- Training is another session's job; this batch is the input. 40 requests over 11 targets is thin for the rarer targets (2 to 3 each): a second seed with Arda's numbers doubles them.
- The 20 unwritten prompts of seed 1 (items 40 to 59) are in the run's draw and can be written in a later batch without redrawing.
- Cost of this run: two Opus writers about 111K bar units each, two Fable judges about 117K each.
