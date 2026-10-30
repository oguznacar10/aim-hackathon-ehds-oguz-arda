# Handoff - decision ablation, live run (2026-10-30, Arda via Claude)

Every number below comes from a run executed today on worktree commit `573297a` (PR 5 merged, `main` at the time the branch was cut). Set: the 10 challenge requests. `--runs 3 --no-cache`, so every decision was a fresh call. Nothing is remembered or estimated.

## Which modes ran

| mode | what it is | ran | who started it | key |
|---|---|---|---|---|
| rules | keyword reader + rules, offline | yes | this session | none |
| hybrid | gpt-4o reads two facts, rules decide (shipped path) | yes | Arda's terminal tab | OpenRouter, via Secret Manager in-process |
| llm | gpt-4o decides end to end (ablation only, never shipped) | yes | Arda's terminal tab | OpenRouter |
| nimble | Nimble 9B via Ollama reads, rules decide | yes | this session | none |
| vote | gpt-4o reads, Nimble second opinion, disagreement escalates | yes | Arda's terminal tab | OpenRouter |
| jev | TypeSafe Jev reads, rules decide | no | - | TypeSafe key; Arda chose the five modes above, jev was not requested |

Nimble note: Ollama 0.40.11 refused the `nimble:latest` pulled on 30 Sep on its `/v1/systemone` endpoint ("downloaded in a format that is no longer supported"; chat still worked). Arda approved a re-pull (9.3 GB, new blob digest `13ae0a50`), after which the endpoint answered 200 and the run went through.

## Commands

Local, no key (this session):

```
env -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u ANTHROPIC_API_KEY python3 scripts/eval_decisions.py --mode rules --no-cache --runs 3
env -u OPENAI_API_KEY -u OPENROUTER_API_KEY -u ANTHROPIC_API_KEY python3 scripts/eval_decisions.py --mode nimble --no-cache --runs 3
```

With the OpenRouter key (Arda's terminal tab, key fetched inside the process, never printed):

```
env -u OPENAI_API_KEY OPENROUTER_API_KEY_SECRET=projects/project-beta-482921/secrets/openrouter python3 scripts/eval_decisions.py --mode hybrid --no-cache --runs 3 --provider openrouter
env -u OPENAI_API_KEY OPENROUTER_API_KEY_SECRET=projects/project-beta-482921/secrets/openrouter python3 scripts/eval_decisions.py --mode llm --no-cache --runs 3 --provider openrouter
env -u OPENAI_API_KEY OPENROUTER_API_KEY_SECRET=projects/project-beta-482921/secrets/openrouter python3 scripts/eval_decisions.py --mode vote --no-cache --runs 3 --provider openrouter
```

## Summary table

Assembled from the five per-mode outputs below (the script prints this table only for `--mode all`, which was not used because the modes ran separately).

| mode | correct | consistent | dangerous / unflagged | restrictive | escalated | p50 s | p95 s | max s |
|---|---|---|---|---|---|---|---|---|
| rules | 10/10 | 10/10 | 0 / 0 | 0 | 0 | 0.00 | 0.00 | 0.00 |
| hybrid | 10/10 | 10/10 | 0 / 0 | 0 | 0 | 1.00 | 2.21 | 2.95 |
| llm | 10/10 | 10/10 | 0 / 0 | 0 | 0 | 1.21 | 1.92 | 2.49 |
| nimble | 10/10 | 10/10 | 0 / 0 | 0 | 0 | 0.01 | 1.10 | 1.25 |
| vote | 10/10 | 10/10 | 0 / 0 | 0 | 0 | 0.99 | 1.48 | 2.74 |

Every mode: 30 decisions, 0 observed failures, so the true failure rate can still be up to 10.0% (rule of three, 95% confidence).

## Per-mode output as printed

```
mode=rules set=challenge cases=10 runs=3 source=keywords cache=off
  R01        APPROVE_STATISTICAL  53,69          ok
  R02        REJECT               54             ok
  R03        APPROVE_STATISTICAL  53,69          ok
  R04        REJECT               54             ok
  R05        APPROVE_SPE          53,66,68,73    ok
  R06        REJECT               54             ok
  R07        APPROVE_STATISTICAL  53,69          ok
  R08        APPROVE_STATISTICAL  53,69          ok
  R09        APPROVE_STATISTICAL  53,66,69       ok
  R10        REJECT               54             ok
correct decisions: 10/10
consistent over 3 runs: 10/10
over all 30 decisions: dangerous (more data than the law allows) 0, invalid 0, of those not flagged for staff 0; restrictive (less than allowed) 0; escalated to staff 0
latency: p50 0.00 s, p95 0.00 s, max 0.00 s
with 30 decisions and 0 observed failures the true failure rate can still be up to 10.0% (rule of three, 95% confidence)
```

```
mode=hybrid set=challenge cases=10 runs=3 source=openrouter cache=off
  R01        APPROVE_STATISTICAL  53,69          ok
  R02        REJECT               54             ok
  R03        APPROVE_STATISTICAL  53,69          ok
  R04        REJECT               54             ok
  R05        APPROVE_SPE          53,66,68,73    ok
  R06        REJECT               54             ok
  R07        APPROVE_STATISTICAL  53,69          ok
  R08        APPROVE_STATISTICAL  53,69          ok
  R09        APPROVE_STATISTICAL  53,66,69       ok
  R10        REJECT               54             ok
correct decisions: 10/10
consistent over 3 runs: 10/10
over all 30 decisions: dangerous (more data than the law allows) 0, invalid 0, of those not flagged for staff 0; restrictive (less than allowed) 0; escalated to staff 0
latency: p50 1.00 s, p95 2.21 s, max 2.95 s
with 30 decisions and 0 observed failures the true failure rate can still be up to 10.0% (rule of three, 95% confidence)
```

```
mode=llm set=challenge cases=10 runs=3 source=openrouter cache=off
  R01        APPROVE_STATISTICAL  53,69          ok
  R02        REJECT               54             ok
  R03        APPROVE_STATISTICAL  53,69          ok
  R04        REJECT               54             ok
  R05        APPROVE_SPE          53,66,68,73    ok
  R06        REJECT               54             ok
  R07        APPROVE_STATISTICAL  53,69          ok
  R08        APPROVE_STATISTICAL  53,69          ok
  R09        APPROVE_STATISTICAL  53,66,69       ok
  R10        REJECT               54             ok
correct decisions: 10/10
consistent over 3 runs: 10/10
over all 30 decisions: dangerous (more data than the law allows) 0, invalid 0, of those not flagged for staff 0; restrictive (less than allowed) 0; escalated to staff 0
latency: p50 1.21 s, p95 1.92 s, max 2.49 s
with 30 decisions and 0 observed failures the true failure rate can still be up to 10.0% (rule of three, 95% confidence)
```

```
mode=nimble set=challenge cases=10 runs=3 source=nimble cache=off
  R01        APPROVE_STATISTICAL  53,69          ok
  R02        REJECT               54             ok
  R03        APPROVE_STATISTICAL  53,69          ok
  R04        REJECT               54             ok
  R05        APPROVE_SPE          53,66,68,73    ok
  R06        REJECT               54             ok
  R07        APPROVE_STATISTICAL  53,69          ok
  R08        APPROVE_STATISTICAL  53,69          ok
  R09        APPROVE_STATISTICAL  53,66,69       ok
  R10        REJECT               54             ok
correct decisions: 10/10
consistent over 3 runs: 10/10
over all 30 decisions: dangerous (more data than the law allows) 0, invalid 0, of those not flagged for staff 0; restrictive (less than allowed) 0; escalated to staff 0
latency: p50 0.01 s, p95 1.10 s, max 1.25 s
with 30 decisions and 0 observed failures the true failure rate can still be up to 10.0% (rule of three, 95% confidence)
```

```
mode=vote set=challenge cases=10 runs=3 source=openrouter+nimble cache=off
  R01        APPROVE_STATISTICAL  53,69          ok
  R02        REJECT               54             ok
  R03        APPROVE_STATISTICAL  53,69          ok
  R04        REJECT               54             ok
  R05        APPROVE_SPE          53,66,68,73    ok
  R06        REJECT               54             ok
  R07        APPROVE_STATISTICAL  53,69          ok
  R08        APPROVE_STATISTICAL  53,69          ok
  R09        APPROVE_STATISTICAL  53,66,69       ok
  R10        REJECT               54             ok
correct decisions: 10/10
consistent over 3 runs: 10/10
over all 30 decisions: dangerous (more data than the law allows) 0, invalid 0, of those not flagged for staff 0; restrictive (less than allowed) 0; escalated to staff 0
latency: p50 0.99 s, p95 1.48 s, max 2.74 s
with 30 decisions and 0 observed failures the true failure rate can still be up to 10.0% (rule of three, 95% confidence)
```

## Honest reading

1. Unflagged dangerous errors: 0 in every mode. That is the number that must be 0, and it is, on this sample.
2. Escalations to staff: 0 in every mode, including vote. gpt-4o and Nimble never disagreed on the two facts for these 10 requests.
3. p95 latency: rules 0.00 s, nimble 1.10 s, vote 1.48 s, llm 1.92 s, hybrid 2.21 s. All far under the 60 s limit. The Nimble p50 of 0.01 s means Ollama kept the model warm; its first call took about 1 s.
4. The 10 requests cannot rank the modes. All five are 10/10, so the sample says nothing about which reader is safer on unseen wording. A ranking needs the synthetic held-out set (PR 16 added the generator; the batch size is Arda's).
5. The local Nimble reader matched the gpt-4o reader on every request with no key and no cloud call. That is a measured fact on 10 requests, not a reason to switch the shipped path.

## What moved while this ran

`main` is now at `8da7689`. PR 15 (`b7b8a70`) changed `reader.py` and `rules.py`: new facts `public_body` and `reserved_purpose_only`, the Art. 53(2) refusal, the tighter Art. 66(3) test, and `PROMPT_VERSION` "2". The hybrid, llm and vote numbers above measure the prompt and rules of `573297a`, not of `main`. A re-run on `main` costs about 90 OpenRouter calls and a few minutes; Arda decides whether it is worth it.

## Not done

- jev mode (not requested).
- Any run on a red-team or synthetic set.
- Re-run on `main` after PR 15.

## Next step

Generate the synthetic test set at Arda's size, run `--mode all --set holdout --no-cache --runs 3` on current `main`, and rank by unflagged dangerous errors, then escalations, then p95.
