import json
import pytest
import apply_guard as ag
CFG = {"auto_submit": True, "submit_threshold": 80, "max_submits_per_run": 5}
def good():
    return {"fit_score": 85, "adapter": "greenhouse", "adapter_manual_only": False, "detection_confidence": 0.95, "captcha_seen": False,
            "login_wall": False, "mfa_prompt": False, "validation_errors": 0, "needs_review_answers": 0, "canary_ok": True,
            "posting_id_matches": True, "pre_submit_screenshot": "evidence/pre.png", "final_control_found": True}
def test_allows_when_all_gates_pass():
    assert ag.decide(good(), CFG, {"submits_this_run": 0})["allow"] is True
def test_every_gate_false_denies():
    for k, v in [("fit_score", 79), ("adapter_manual_only", True), ("detection_confidence", 0.5), ("captcha_seen", True), ("login_wall", True),
                 ("mfa_prompt", True), ("validation_errors", 1), ("needs_review_answers", 1), ("canary_ok", False), ("posting_id_matches", False),
                 ("pre_submit_screenshot", None), ("final_control_found", False)]:
        s = good(); s[k] = v
        d = ag.decide(s, CFG, {"submits_this_run": 0})
        assert d["allow"] is False and d["reason_codes"], k
def test_auto_submit_off_and_cap_and_i_mean_it():
    assert ag.decide(good(), dict(CFG, auto_submit=False), {"submits_this_run": 0})["allow"] is False
    assert ag.decide(good(), dict(CFG, auto_submit=False), {"submits_this_run": 0}, i_mean_it=True)["allow"] is True
    assert ag.decide(good(), CFG, {"submits_this_run": 5})["allow"] is False
    s = good(); s["fit_score"] = 50
    assert ag.decide(s, dict(CFG, auto_submit=False), {"submits_this_run": 0}, i_mean_it=True)["allow"] is True  # explicit human override of fit only
    s["needs_review_answers"] = 1
    assert ag.decide(s, CFG, {"submits_this_run": 0}, i_mean_it=True)["allow"] is False  # never with unreviewed answers
def test_reserve_slot_is_capped(home):
    assert ag.reserve_slot(home, "run1", "fpA", 2) and ag.reserve_slot(home, "run1", "fpB", 2)
    assert ag.reserve_slot(home, "run1", "fpC", 2) is False
    assert ag.submits_this_run(home, "run1") == 2

# --- Fix Round 1 regression tests -------------------------------------------------

def test_reserve_slot_atomic_under_concurrency(home):
    # C1: 8 concurrent reservations against a cap of 3 must grant exactly 3, never more,
    # via append-then-verify (no separate lock file that could itself race or crash-leak).
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda i: ag.reserve_slot(home, "runC", f"fp{i}", 3), range(8)))
    assert sum(1 for r in results if r) == 3
    assert ag.submits_this_run(home, "runC") == 3

def test_missing_required_key_denies_incomplete_state():
    # C2: a state dict missing a required key must fail closed, not be silently treated
    # as falsy/False for that gate.
    s = good(); del s["needs_review_answers"]
    d = ag.decide(s, CFG, {"submits_this_run": 0})
    assert d["allow"] is False and "incomplete_state" in d["reason_codes"]

def test_stringly_bool_denies_bad_state_types():
    # C2: "false" is truthy in Python — a gate must never accept a non-bool stand-in.
    s = good(); s["canary_ok"] = "false"
    d = ag.decide(s, CFG, {"submits_this_run": 0})
    assert d["allow"] is False and "bad_state_types" in d["reason_codes"]

def test_stringly_int_is_coerced_and_allows():
    # C2: a stringly counter that coerces cleanly (int("0") == 0) must not be denied.
    s = good(); s["validation_errors"] = "0"
    d = ag.decide(s, CFG, {"submits_this_run": 0})
    assert d["allow"] is True

def test_cli_decide_bad_state_json_exits_3(home, tmp_path, capsys):
    # I3: malformed --state-json must never traceback; it must deny with a bad_state code.
    bad = tmp_path / "state.json"
    bad.write_text("not json")
    with pytest.raises(SystemExit) as exc:
        ag.main(["--home", str(home), "decide", "--state-json", str(bad), "--run", "runbad"])
    assert exc.value.code == 3
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["allow"] is False and out["reason_codes"] == ["bad_state"]

# --- Fix Round 2 regression tests -------------------------------------------------

def test_stringly_fit_score_is_coerced_and_allows():
    # Item 1: "85" (string) must coerce cleanly via float(), not traceback at the
    # threshold comparison.
    s = good(); s["fit_score"] = "85"
    d = ag.decide(s, CFG, {"submits_this_run": 0})
    assert d["allow"] is True

def test_non_numeric_fit_score_denies_bad_state_types():
    # Item 1: an uncoercible fit_score must fail closed, never traceback.
    s = good(); s["fit_score"] = "eighty"
    d = ag.decide(s, CFG, {"submits_this_run": 0})
    assert d["allow"] is False and "bad_state_types" in d["reason_codes"]

def test_bool_fit_score_denies_bad_state_types():
    # bonus: bool is an int subclass — True/False must never silently coerce to 1/0.
    s = good(); s["fit_score"] = True
    d = ag.decide(s, CFG, {"submits_this_run": 0})
    assert d["allow"] is False and "bad_state_types" in d["reason_codes"]

def test_cli_decide_non_numeric_fit_score_exits_3_with_json(home, tmp_path, capsys):
    # Item 1: a well-formed state.json with a bad fit_score must exit 3 with valid JSON
    # on stdout, never a traceback.
    s = good(); s["fit_score"] = "eighty"
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(s))
    with pytest.raises(SystemExit) as exc:
        ag.main(["--home", str(home), "decide", "--state-json", str(state_file), "--run", "runFit"])
    assert exc.value.code == 3
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["allow"] is False

def test_cli_decide_never_tracebacks_on_internal_error(home, tmp_path, capsys, monkeypatch):
    # Item 1: the CLI wraps the whole decide() call, so even an unexpected internal
    # failure fails closed as bad_state instead of raising.
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(good()))
    def boom(*a, **kw):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(ag, "decide", boom)
    with pytest.raises(SystemExit) as exc:
        ag.main(["--home", str(home), "decide", "--state-json", str(state_file), "--run", "runBoom"])
    assert exc.value.code == 3
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["allow"] is False and out["reason_codes"] == ["bad_state"]

def test_released_slots_are_not_burned_forever(home):
    # Item 3: reserve 3 at cap 3, release all 3, then a 4th reservation must succeed
    # because the cap counts active (unreleased) reservations, not lifetime history.
    assert ag.reserve_slot(home, "runR", "fp1", 3)
    assert ag.reserve_slot(home, "runR", "fp2", 3)
    assert ag.reserve_slot(home, "runR", "fp3", 3)
    assert ag.submits_this_run(home, "runR") == 3
    ag.release_slot(home, "runR", "fp1")
    ag.release_slot(home, "runR", "fp2")
    ag.release_slot(home, "runR", "fp3")
    assert ag.submits_this_run(home, "runR") == 0
    assert ag.reserve_slot(home, "runR", "fp4", 3) is True
    assert ag.submits_this_run(home, "runR") == 1

def test_reserve_slot_atomic_under_concurrency_still_exact(home):
    # Item 3 regression guard: the active-row filtering change must not break the
    # original concurrency guarantee when nothing has ever been released.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda i: ag.reserve_slot(home, "runC2", f"fp{i}", 3), range(8)))
    assert sum(1 for r in results if r) == 3
    assert ag.submits_this_run(home, "runC2") == 3
