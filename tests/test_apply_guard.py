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
