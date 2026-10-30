"""Drives gatekeeper.synth with Claude Code agents as writer and judge instead of API calls.

  draw     --n N --seed S --max-attempts M --work DIR   -> DIR/draw.json (shapes, targets, writer prompts)
  assemble --work DIR                                   -> reads DIR/prose.json, writes DIR/judge.json + invalid/
  route    --work DIR --out OUT                         -> reads DIR/verdicts.json, writes OUT/{tuning,holdout,disputed}

Phase 1 output has max_attempts items; agents write prose for the first ones until N survive.
"""
import argparse
import json
import random
from pathlib import Path

from gatekeeper import planner, query, redteam, synth


def draw(n, seed, max_attempts, work):
    rng = random.Random(seed)
    items = []
    for i in range(max_attempts):
        target = synth._pick(rng, synth.TARGETS)
        shape = synth.build_shape(rng, target["shape"])
        items.append({"i": i, "target": target["name"], "shape": shape,
                      "prompt": synth.writer_prompt(shape, target), "stamp_seed": f"{seed}-{i}"})
    work.mkdir(parents=True, exist_ok=True)
    (work / "draw.json").write_text(json.dumps({"n": n, "seed": seed, "items": items}, indent=1,
                                               ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"drawn": len(items), "n": n}))


def assemble(work):
    drawn = json.loads((work / "draw.json").read_text(encoding="utf-8"))
    prose = {p["i"]: p for p in json.loads((work / "prose.json").read_text(encoding="utf-8"))}
    vocab = redteam.vocabulary()
    targets = {t["name"]: t for t in synth.TARGETS}
    stats = {"kept": 0, "invalid": 0, "malformed": 0, "unwritten": 0}
    kept, seen = [], set()
    for item in drawn["items"]:
        if stats["kept"] >= drawn["n"]:
            break
        p = prose.get(item["i"])
        if p is None:
            stats["unwritten"] += 1
            continue
        if not isinstance(p.get("purpose"), str) or not isinstance(p.get("applicant"), dict):
            stats["malformed"] += 1
            continue
        target = targets[item["target"]]
        req = synth.assemble(item["shape"], target, p, random.Random(item["stamp_seed"]))
        if req["id"] in seen:
            stats["malformed"] += 1
            continue
        seen.add(req["id"])
        problems = redteam.validate_generated(req, vocab)
        if not problems:
            try:
                result = synth.answer(req)
            except (planner.PlanningFailed, query.InvalidPlan) as e:
                problems = [f"the data cannot answer it: {e}"]
        if problems:
            stats["invalid"] += 1
            synth._write(work / "invalid", req["id"], {**req, "target": target["name"], "problems": problems})
            continue
        req["expected"] = synth.label(req, target)
        req["target"] = target["name"]
        req["answer"] = result
        kept.append(req)
        stats["kept"] += 1
    (work / "labelled.json").write_text(json.dumps(kept, indent=1, ensure_ascii=False), encoding="utf-8")
    judge_items = [{"id": r["id"], "request": synth.judge_input(r),
                    "prompt": redteam.JUDGE_PROMPT.format(request=json.dumps(synth.judge_input(r), ensure_ascii=False))}
                   for r in kept]
    (work / "judge.json").write_text(json.dumps(judge_items, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(stats))


def route(work, out):
    kept = json.loads((work / "labelled.json").read_text(encoding="utf-8"))
    verdicts = {v["id"]: v for v in json.loads((work / "verdicts.json").read_text(encoding="utf-8"))}
    stats = {"tuning": 0, "holdout": 0, "disputed": 0, "unjudged": 0}
    for req in kept:
        v = verdicts.get(req["id"])
        if v is None:
            stats["unjudged"] += 1
            continue
        req["judge"] = {"decision": v.get("decision"), "why": v.get("why", "")}
        folder = "holdout" if redteam.is_holdout({k: req[k] for k in req if k != "judge"}) else "tuning"
        if req["judge"]["decision"] != req["expected"]["decision"]:
            folder = "disputed"
        stats[folder] += 1
        synth._write(out / folder, req["id"], req)
    print(json.dumps(stats))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draw")
    d.add_argument("--n", type=int, required=True)
    d.add_argument("--seed", type=int, required=True)
    d.add_argument("--max-attempts", type=int, required=True)
    d.add_argument("--work", required=True)
    a = sub.add_parser("assemble")
    a.add_argument("--work", required=True)
    r = sub.add_parser("route")
    r.add_argument("--work", required=True)
    r.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "draw":
        draw(args.n, args.seed, args.max_attempts, Path(args.work))
    elif args.cmd == "assemble":
        assemble(Path(args.work))
    else:
        route(Path(args.work), Path(args.out))


if __name__ == "__main__":
    main()
