"""One request in, one answer out: read, decide, then compute statistics or build the SPE."""
import json

from gatekeeper import llm, planner, query, reader, rules, spe


def _plan(request, mode, provider):
    """LLM plan when a key is set, rule plan otherwise; both when possible, flagged if they differ."""
    build = planner.rule_statistics_plan if mode == "statistics" else planner.rule_spe_spec
    rule_plan, rule_error = None, None
    try:
        rule_plan = build(request)
    except (planner.PlanningFailed, query.InvalidPlan) as e:
        rule_error = str(e)
    if provider is None:
        if rule_plan is None:
            raise planner.PlanningFailed(f"no LLM configured and the rule planner failed: {rule_error}")
        return rule_plan, "rules", None
    try:
        ai_plan = planner.llm_plan(request, mode, provider)
    except (query.InvalidPlan, llm.LLMUnavailable, ValueError, OSError) as e:
        if rule_plan is None:
            raise planner.PlanningFailed(
                f"LLM plan failed ({e}) and the rule planner failed: {rule_error}") from e
        return rule_plan, "rules", f"LLM plan unusable, rule plan used: {e}"
    return ai_plan, provider, rule_plan


def handle(request, provider=None):
    rules.validate(request)
    providers = llm.available_providers()
    provider = provider or (providers[0] if providers else None)
    reading = reader.read(request, provider)
    result = rules.decide(request, reading)
    out = {"id": request["id"], **result, "reader": reading["source"], "answer": None}
    if result["decision"] == "REJECT":
        return out

    if result["decision"] == "APPROVE_STATISTICAL":
        plan, source, other = _plan(request, "statistics", provider)
        run = query.run(plan)
        out["answer"] = run["answer"]
        out["staff"] = {"plan": plan, "planner": source, "sql": run["sql"]}
        check = _cross_check(other, run["answer"], lambda p: query.run(p)["answer"])
    else:
        spec, source, other = _plan(request, "spe", provider)
        manifest = spe.create(request["id"], spec)
        out["answer"] = {"cohort_size": manifest["cohort_size"]}
        out["staff"] = {"spec": spec, "planner": source, "spe": manifest}
        check = _cross_check(other, manifest["cohort_size"], _cohort_size)
    if check:
        out["needs_staff_review"] = True
        out["staff"]["review_note"] = check
    return out


def _cohort_size(spec):
    return query.run({"population": spec["cohort"],
                      "measures": [{"name": "n", "kind": "count"}]})["answer"]["n"]


def _cross_check(other, answer, compute):
    """other: the rule plan to compare with, a note string, or None."""
    if other is None:
        return None
    if isinstance(other, str):
        return other
    theirs = compute(other)
    if json.dumps(_values(theirs), sort_keys=True) != json.dumps(_values(answer), sort_keys=True):
        return "The LLM plan and the rule plan give different numbers; check the plan before release."
    return None


def _values(node):
    """Values per group, ignoring measure names, which the two planners choose differently."""
    if not isinstance(node, dict):
        return node
    if any(isinstance(v, dict) for v in node.values()):
        return {k: _values(v) for k, v in node.items()}
    return sorted(map(str, node.values()))
