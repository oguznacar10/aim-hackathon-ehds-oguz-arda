"""Generated training requests: built from the data, answerable by the planner, labelled by the rules."""
import json
import random

import pytest

from gatekeeper import redteam, rules, synth

VOCAB = redteam.vocabulary()


def stub_writer(shape, target):
    """Stands in for the LLM: a person applicant and a purpose that names the target."""
    return {"applicant": {"name": "Dr. Test Person", "organisation": "Test Institute (university)",
                          "country": "AT"},
            "purpose": f"Purpose written for target {target['name']} about {shape['topic']}."}


def test_pairs_use_only_codes_that_exist():
    icd = [c for c, _ in VOCAB["icd10"]]
    atc = [c for c, _ in VOCAB["atc"]]
    loinc = [c for c, _ in VOCAB["loinc"]]
    for prefix, (_, meds, obs) in synth.PAIRS.items():
        assert any(c.startswith(prefix) for c in icd), prefix
        for m, _ in meds:
            assert any(c.startswith(m) for c in atc), m
        for o, _ in obs:
            assert o in loinc, o


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_every_shape_passes_the_validator_and_runs_on_the_data(seed):
    rng = random.Random(seed)
    for _ in range(12):
        for kind in ("table", "records"):
            shape = synth.build_shape(rng, kind)
            req = synth.assemble(shape, synth.TARGETS[0], stub_writer(shape, synth.TARGETS[0]), rng)
            assert redteam.validate_generated(req, VOCAB) == [], req["definitions"]
            answer = synth.answer(req)
            assert answer, req["question"]


def test_targets_label_as_intended_through_the_rules():
    rng = random.Random(7)
    for target in synth.TARGETS:
        shape = synth.build_shape(rng, target["shape"])
        req = synth.assemble(shape, target, stub_writer(shape, target), rng)
        label = synth.label(req, target)
        assert label["decision"] == target["decision"], target["name"]
        assert label["articles"]
        assert label["reason"]
    reserved = next(t for t in synth.TARGETS if t["name"] == "private_reserved_purpose")
    shape = synth.build_shape(rng, reserved["shape"])
    req = synth.assemble(shape, reserved, stub_writer(shape, reserved), rng)
    assert synth.label(req, reserved)["articles"] == ["53"]


def test_records_targets_never_ask_for_a_table():
    rng = random.Random(3)
    for target in synth.TARGETS:
        if target["decision"] != "APPROVE_SPE":
            continue
        shape = synth.build_shape(rng, target["shape"])
        assert not any(d.lower().startswith("report per") for d in shape["definitions"])


def test_generate_writes_labelled_files(tmp_path):
    stats = synth.generate(6, 11, stub_writer, out=tmp_path)
    files = sorted(tmp_path.glob("*/*.json"))
    assert stats["kept"] == len(files) == 6
    assert stats["invalid"] == 0
    ids = set()
    for f in files:
        req = json.loads(f.read_text(encoding="utf-8"))
        rules.validate(req)
        assert req["id"].startswith("S") and req["id"] not in ids
        ids.add(req["id"])
        assert req["submitted"].startswith("2026-10-")
        assert set(req["expected"]) == {"decision", "articles", "reason"}
        assert req["expected"]["decision"] in redteam.DECISIONS
        assert "intended" not in req and "judge" not in req
        assert f.parent.name in ("tuning", "holdout")


def test_generate_is_deterministic_for_a_seed(tmp_path):
    synth.generate(3, 5, stub_writer, out=tmp_path / "a")
    synth.generate(3, 5, stub_writer, out=tmp_path / "b")
    a = sorted(p.name for p in (tmp_path / "a").glob("*/*.json"))
    b = sorted(p.name for p in (tmp_path / "b").glob("*/*.json"))
    assert a == b and len(a) == 3


def test_judge_disagreement_goes_to_disputed(tmp_path):
    def contrary_judge(req):
        return {"decision": "REJECT" if req["expected"]["decision"] != "REJECT" else "APPROVE_SPE",
                "why": "test"}
    stats = synth.generate(4, 2, stub_writer, judge=contrary_judge, out=tmp_path)
    assert stats["disputed"] == 4
    for f in tmp_path.glob("disputed/*.json"):
        req = json.loads(f.read_text(encoding="utf-8"))
        assert req["judge"]["decision"] != req["expected"]["decision"]


def test_writer_prompt_never_sees_patient_rows_and_names_the_target():
    rng = random.Random(1)
    shape = synth.build_shape(rng, "table")
    prompt = synth.writer_prompt(shape, synth.TARGETS[0])
    assert synth.TARGETS[0]["brief"] in prompt
    assert "patient_id" not in prompt and "P0" not in prompt
