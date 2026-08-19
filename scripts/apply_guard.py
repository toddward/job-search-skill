#!/usr/bin/env python3
"""Deterministic submit guard. The skill may only click a final submit control when decide() returns allow=True."""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import common

def decide(state: dict, cfg_apply: dict, run_state: dict, i_mean_it: bool = False) -> dict:
    codes, reasons = [], []
    def deny(code, msg): codes.append(code); reasons.append(msg)
    if not i_mean_it:
        if not cfg_apply.get("auto_submit"):
            deny("auto_submit_off", "apply.auto_submit is false")
        if (state.get("fit_score") or 0) < cfg_apply.get("submit_threshold", 80):
            deny("below_threshold", f"fit {state.get('fit_score')} < threshold {cfg_apply.get('submit_threshold', 80)}")
        if run_state.get("submits_this_run", 0) >= cfg_apply.get("max_submits_per_run", 5):
            deny("cap_reached", "per-run submit cap reached")
    if state.get("adapter_manual_only"):
        deny("manual_only", f"{state.get('adapter')} is manual-only (platform terms)")
    if (state.get("detection_confidence") or 0) < 0.85:
        deny("low_confidence", "ATS detection confidence < 0.85")
    for k, code in (("captcha_seen", "captcha"), ("login_wall", "login_wall"), ("mfa_prompt", "mfa")):
        if state.get(k): deny(code, f"{k} present")
    if state.get("validation_errors", 0):
        deny("validation_errors", f"{state['validation_errors']} inline validation error(s)")
    if state.get("needs_review_answers", 0):
        deny("needs_review", f"{state['needs_review_answers']} AI-drafted answer(s) await review")
    if not state.get("canary_ok", False):
        deny("canary", "canary/injection check failed or not run")
    if not state.get("posting_id_matches", False):
        deny("posting_mismatch", "posting id/URL no longer matches the draft")
    if not state.get("pre_submit_screenshot"):
        deny("no_evidence", "no pre-submit screenshot")
    if not state.get("final_control_found", False):
        deny("no_final_control", "final submit control not positively identified")
    return {"allow": not codes, "reason_codes": codes, "reasons": reasons}

def _slot_file(home: Path, run_id: str) -> Path:
    return Path(home) / "memory" / f".submits-{run_id}.jsonl"

def submits_this_run(home: Path, run_id: str) -> int:
    return len([r for r in common.read_jsonl(_slot_file(home, run_id)) if r.get("reserved")])

def reserve_slot(home: Path, run_id: str, fp: str, cap: int) -> bool:
    f = _slot_file(home, run_id); f.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(f) + ".lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY) if not os.path.exists(str(f) + ".lock") else None
    try:
        if submits_this_run(home, run_id) >= cap:
            return False
        common.append_jsonl(f, {"fp": fp, "reserved": True, "at": common.utcnow()})
        return True
    finally:
        if fd is not None:
            os.close(fd); os.unlink(str(f) + ".lock")

def record_result(home: Path, run_id: str, fp: str, submitted: bool, reason: str = "") -> None:
    common.append_jsonl(_slot_file(home, run_id), {"fp": fp, "submitted": submitted, "reason": reason, "at": common.utcnow()})
    common.append_jsonl(Path(home) / "memory" / "logs" / "submits.jsonl", {"run_id": run_id, "fp": fp, "submitted": submitted, "reason": reason, "at": common.utcnow()})

def main(argv=None):
    import argparse, config
    ap = argparse.ArgumentParser(description="submit guard"); ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide"); d.add_argument("--state-json", required=True); d.add_argument("--run", required=True); d.add_argument("--i-mean-it", action="store_true")
    r = sub.add_parser("reserve"); r.add_argument("--run", required=True); r.add_argument("--fp", required=True)
    rec = sub.add_parser("record"); rec.add_argument("--run", required=True); rec.add_argument("--fp", required=True); rec.add_argument("--submitted", action="store_true"); rec.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    home = common.data_home(a.home); cfg = config.load(home)["apply"]
    if a.cmd == "decide":
        state = json.loads(Path(a.state_json).read_text())
        out = decide(state, cfg, {"submits_this_run": submits_this_run(home, a.run)}, a.i_mean_it)
        print(json.dumps(out)); sys.exit(0 if out["allow"] else 3)
    if a.cmd == "reserve":
        ok = reserve_slot(home, a.run, a.fp, cfg.get("max_submits_per_run", 5)); print(json.dumps({"reserved": ok})); sys.exit(0 if ok else 3)
    if a.cmd == "record":
        record_result(home, a.run, a.fp, a.submitted, a.reason); print("ok")

if __name__ == "__main__":
    main()
