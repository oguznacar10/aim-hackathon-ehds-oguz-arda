# Handoff - synthetic request run 1 (2026-10-30, Arda via Claude)

## What changed
- `synth/tuning/` (25 files), `synth/holdout/` (11 files) and `synth/disputed/` (4 files, moved there after the blind review, see below): the first batch of labelled synthetic requests. Run: N 40, seed 1, max-attempts 60; the first 40 prompts were used, 20 were never written.
- `scripts/synth_agents.py`: drives `gatekeeper.synth` in three phases (`draw`, `assemble`, `route`) with Claude Code agents as writer and judge instead of API calls. Writers were two Opus 5.5 agents (30 prompts each), judges two Fable 5.1 agents (20 requests each). Writers saw only the writer prompt; judges saw only `redteam.JUDGE_PROMPT` with the request fields (`synth.judge_input`, no expected, target or answer).
- `scripts/eval_decisions.py`: `--set` takes a path such as `synth/tuning` and reads a dict `expected` as decision plus articles, so articles are scored on synthetic sets too.
- `docs/MAP.md`: one line for the driver.

## Run statistics (from the run, not from memory)
- assemble: kept 40, invalid 0, malformed 0, unwritten 0 (of 60 drawn, 40 used).
- route: tuning 29, holdout 11, disputed 0; the judges agreed with the rules label on all 40. After the blind review 4 tuning files moved to disputed (tuning 25).
- Targets kept: reject_54c 5, spe_mechanism 5, private_reserved_purpose 5, reject_54b 5, reject_54d 4, reject_54a 4, spe_public 3, app_bare_claim 3, stat_research 2, app_no_claim 2, stat_public 2.
- Decisions kept: REJECT 23, APPROVE_STATISTICAL 9, APPROVE_SPE 8.

## Offline eval (3 runs each, no key)
- `--mode rules` (keyword reader + rules): tuning 14/25 correct, 25/25 consistent, 21 dangerous unflagged of 75; holdout 4/11, 11/11 consistent, 9 dangerous unflagged of 33. Misses by target: spe_mechanism 5, reject_54a 4, private_reserved_purpose 4, reject_54b 3, spe_public 3, reject_54c 2. The keyword reader cannot see an innocently worded prohibited purpose or a mechanism sentence; that is what the set is for.
- `--mode nimble` (Nimble reads through Ollama, rules decide): tuning 22/25 correct, 25/25 consistent, 9 dangerous unflagged of 75, 0 restrictive; holdout 9/11, 11/11 consistent, 3 dangerous unflagged of 33, 3 restrictive. Misses by target: private_reserved_purpose 5, reject_54b 2, reject_54a 1, spe_public 1. Latency p95 under 1 s (cache on after run 1).

## Hand read of 10 kept requests
- Purposes read like real applications and fit their question. Prohibited targets are dressed as business language (communication plans, consumer research, credit scoring) but still name the purpose outright (sales visits, loan pricing, premiums), so they are easy negatives, not hard ones.
- SPE purposes name a concrete mechanism (sequence training, longitudinal linkage); the 53(2) insurer case claims a policy purpose plausibly.
- Weak spots: the spirits and e-cigarette cases tie the product to the health question loosely; one insurer purpose would pass as research if read generously.

## Blind review (Fable, same day) and what changed
- Art. 53(2) reserves public-health, policy and statistics purposes to public bodies "including where processing ... is done by a third party on behalf of those public sector bodies" (`docs/challenge/ehds-articles/art-53.md`). 4 of the 5 private_reserved_purpose files describe exactly that: a private contractor working for a federal state or health authority (S02d73635, S17d8f076, S882325ec, Sfa328edb). Their REJECT [53] label is contestable, so they moved to `synth/disputed/` with a `review` note; the log has a PROPOSED entry. Neither `rules.py` nor `redteam.JUDGE_PROMPT` knows the clause.
- 0 disputed of 40 is structurally expected, not evidence of label quality: label and judge apply the same ordered rules, and the SPE/STAT split is fixed by requested_as plus the shape. Only REJECT versus allowed is a real test. Judge blinding verified at code level (`synth.judge_input`); the judge agents had filesystem access in a work dir that also held the labels, which the repo cannot prove they did not read.
- Driver divergence (harmless): `assemble` stops at N kept before judging, so disputed files shrink the batch below N, whereas `generate()` counts kept plus disputed.
- Counts over all 40 checked by script: no duplicate purposes, names or ids; every applicant a titled person with an organisation kind and a country; 0 em-dashes; all `submitted` in October 2026 with the right offset; eval loader byte-identical to main on the challenge and redteam sets.

## Not verified
- `--mode hybrid`, `--mode llm`, `--mode vote` need the OpenRouter key and are Arda's to run from his terminal:
  `OPENROUTER_API_KEY_SECRET=projects/project-beta-482921/secrets/openrouter PYTHONPATH=src python3 scripts/eval_decisions.py --set synth/tuning --mode hybrid --runs 3` (then `--mode llm`, `--mode vote`, and `--set synth/holdout`).
- No human tick of `synth/holdout/` yet. Judge agreement is not a human review.

## Open / next
- Training is another session's job; this batch is the input. 40 requests over 11 targets is thin for the rarer targets (2 to 3 each): a second seed with Arda's numbers doubles them.
- The 20 unwritten prompts of seed 1 (items 40 to 59) are in the run's draw and can be written in a later batch without redrawing.
- Cost of this run: two Opus writers about 111K bar units each, two Fable judges about 117K each.

## Update 2026-10-30 - Art. 53(2) third-party clause decided
- `S17d8f076` relabelled by `rules.decide()` with the keyword reader to APPROVE_STATISTICAL [53, 69], flagged for staff to verify the mandate, and moved to `synth/tuning/` (tuning 26, disputed 3). The offline eval numbers above were measured on the 25-file tuning set and were not re-run.
- `S02d73635`, `S882325ec`, `Sfa328edb` stay in `synth/disputed/`: the keyword reader does not read their purpose as reserved for public bodies. See the DECIDED entry in `docs/decisions/log.md`.
