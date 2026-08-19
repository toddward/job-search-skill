#!/usr/bin/env python3
"""Deterministic submit guard. The skill may only click a final submit control when decide() returns allow=True."""
from __future__ import annotations
import json, os, sys, uuid
from pathlib import Path
import common

REQUIRED_STATE_KEYS = ["fit_score", "adapter", "adapter_manual_only", "detection_confidence", "captcha_seen",
                       "login_wall", "mfa_prompt", "validation_errors", "needs_review_answers", "canary_ok",
                       "posting_id_matches", "pre_submit_screenshot", "final_control_found"]
_BOOL_KEYS = ("captcha_seen", "login_wall", "mfa_prompt", "canary_ok", "posting_id_matches",
              "final_control_found", "adapter_manual_only")
_INT_KEYS = ("validation_errors", "needs_review_answers")

def decide(state: dict, cfg_apply: dict, run_state: dict, i_mean_it: bool = False) -> dict:
    codes, reasons = [], []
    def deny(code, msg): codes.append(code); reasons.append(msg)

    missing = [k for k in REQUIRED_STATE_KEYS if k not in state]
    if missing:
        deny("incomplete_state", f"missing required state key(s): {', '.join(missing)}")
        return {"allow": False, "reason_codes": codes, "reasons": reasons}

    # Fail closed on stringly/wrong-typed gate values instead of silently coercing them true/false.
    norm = dict(state)
    bad_types = [k for k in _BOOL_KEYS if state.get(k) is not True and state.get(k) is not False]
    for k in _INT_KEYS:
        try:
            norm[k] = int(state[k])
        except (TypeError, ValueError):
            bad_types.append(k)
    try:
        norm["detection_confidence"] = float(state["detection_confidence"])
    except (TypeError, ValueError):
        bad_types.append("detection_confidence")
    if bad_types:
        deny("bad_state_types", f"non-bool/uncoercible state value(s): {', '.join(sorted(set(bad_types)))}")
        return {"allow": False, "reason_codes": codes, "reasons": reasons}
    state = norm

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

def _read_slots(path: Path) -> list[dict]:
    """Tolerant jsonl reader: a corrupt/unparseable line is skipped, not fatal."""
    out = []
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out

def submits_this_run(home: Path, run_id: str) -> int:
    rows = _read_slots(_slot_file(home, run_id))
    reserved = sum(1 for r in rows if r.get("reserved") is True)
    released = sum(1 for r in rows if r.get("release") is True)
    return max(0, reserved - released)

def release_slot(home: Path, run_id: str, fp: str, nonce: str | None = None) -> None:
    common.append_jsonl(_slot_file(home, run_id), {"fp": fp, "release": True, "nonce": nonce, "at": common.utcnow()})

def reserve_slot(home: Path, run_id: str, fp: str, cap: int) -> bool:
    """Atomic-enough for concurrent callers: each reservation is a single O_APPEND write
    carrying a unique nonce, then the file is re-read and the writer's own row is located
    by that nonce. Only the first `cap` reserved rows (in file order) are granted; a
    caller that loses the race appends a release row for its own reservation and returns
    False. No separate lock file — the append itself is the atomic operation."""
    f = _slot_file(home, run_id); f.parent.mkdir(parents=True, exist_ok=True)
    nonce = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    common.append_jsonl(f, {"fp": fp, "reserved": True, "nonce": nonce, "at": common.utcnow()})
    reserved_rows = [r for r in _read_slots(f) if r.get("reserved") is True]
    idx = next((i for i, r in enumerate(reserved_rows) if r.get("nonce") == nonce), len(reserved_rows))
    if idx < cap:
        return True
    release_slot(home, run_id, fp, nonce)
    return False

def record_result(home: Path, run_id: str, fp: str, submitted: bool, reason: str = "") -> None:
    common.append_jsonl(_slot_file(home, run_id), {"fp": fp, "submitted": submitted, "reason": reason, "at": common.utcnow()})
    common.append_jsonl(Path(home) / "memory" / "logs" / "submits.jsonl", {"run_id": run_id, "fp": fp, "submitted": submitted, "reason": reason, "at": common.utcnow()})

def main(argv=None):
    import argparse, config
    ap = argparse.ArgumentParser(description="submit guard"); ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide"); d.add_argument("--state-json", required=True); d.add_argument("--run", required=True); d.add_argument("--i-mean-it", action="store_true")
    r = sub.add_parser("reserve"); r.add_argument("--run", required=True); r.add_argument("--fp", required=True)
    rel = sub.add_parser("release"); rel.add_argument("--run", required=True); rel.add_argument("--fp", required=True); rel.add_argument("--nonce", default=None)
    rec = sub.add_parser("record"); rec.add_argument("--run", required=True); rec.add_argument("--fp", required=True); rec.add_argument("--submitted", action="store_true"); rec.add_argument("--reason", default="")
    a = ap.parse_args(argv)
    home = common.data_home(a.home); cfg = config.load(home)["apply"]
    if a.cmd == "decide":
        try:
            state = json.loads(Path(a.state_json).read_text())
            if not isinstance(state, dict):
                raise ValueError("state JSON must be an object")
        except (OSError, ValueError) as e:
            out = {"allow": False, "reason_codes": ["bad_state"], "reasons": [f"could not load state JSON: {e}"]}
            print(json.dumps(out)); sys.exit(3)
        out = decide(state, cfg, {"submits_this_run": submits_this_run(home, a.run)}, a.i_mean_it)
        print(json.dumps(out)); sys.exit(0 if out["allow"] else 3)
    if a.cmd == "reserve":
        ok = reserve_slot(home, a.run, a.fp, cfg.get("max_submits_per_run", 5)); print(json.dumps({"reserved": ok})); sys.exit(0 if ok else 3)
    if a.cmd == "release":
        release_slot(home, a.run, a.fp, a.nonce); print("ok")
    if a.cmd == "record":
        record_result(home, a.run, a.fp, a.submitted, a.reason); print("ok")

if __name__ == "__main__":
    main()
