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
_FLOAT_KEYS = ("detection_confidence", "fit_score")
# Platform ToS forbid automating these apply flows: deny on the adapter NAME, so a caller that
# forgets (or fakes) adapter_manual_only cannot talk the guard into a click.
MANUAL_ONLY_ADAPTERS = {"linkedin-easy-apply", "indeed-apply", "linkedin", "indeed"}

def decide(state: dict, cfg_apply: dict, run_state: dict, i_mean_it: bool = False) -> dict:
    codes, reasons = [], []
    def deny(code, msg): codes.append(code); reasons.append(msg)

    missing = [k for k in REQUIRED_STATE_KEYS if k not in state]
    if missing:
        deny("incomplete_state", f"missing required state key(s): {', '.join(missing)}")
        return {"allow": False, "reason_codes": codes, "reasons": reasons}

    # Fail closed on stringly/wrong-typed gate values instead of silently coercing or
    # tracebacking. bool is an int subclass in Python, so it must be rejected explicitly
    # before int()/float() would otherwise happily coerce True/False to 1/0.
    norm = dict(state)
    bad_types = [k for k in _BOOL_KEYS if state.get(k) is not True and state.get(k) is not False]
    for k in _INT_KEYS:
        v = state.get(k)
        if isinstance(v, bool):
            bad_types.append(k); continue
        try:
            norm[k] = int(v)
        except (TypeError, ValueError):
            bad_types.append(k)
    for k in _FLOAT_KEYS:
        v = state.get(k)
        if isinstance(v, bool):
            bad_types.append(k); continue
        try:
            norm[k] = float(v)
        except (TypeError, ValueError):
            bad_types.append(k)
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
    if state.get("adapter_manual_only") or str(state.get("adapter") or "").strip().lower() in MANUAL_ONLY_ADAPTERS:
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
    """Release a previously reserved slot so it stops counting toward the cap. If `nonce`
    is omitted, resolve it to the most recent still-unreleased reservation for this `fp`
    (so a caller — e.g. the CLI — that only knows the fingerprint can still release the
    right row)."""
    f = _slot_file(home, run_id)
    if nonce is None:
        rows = _read_slots(f)
        released_nonces = {r.get("nonce") for r in rows if r.get("release") is True and r.get("nonce")}
        candidates = [r for r in rows if r.get("reserved") is True and r.get("fp") == fp and r.get("nonce") not in released_nonces]
        if candidates:
            nonce = candidates[-1].get("nonce")
    common.append_jsonl(f, {"fp": fp, "release": True, "nonce": nonce, "at": common.utcnow()})

def reserve_slot(home: Path, run_id: str, fp: str, cap: int) -> bool:
    """Atomic-enough for concurrent callers: each reservation is a single O_APPEND write
    carrying a unique nonce, then the file is re-read and the writer's own row is located
    by that nonce among still-active (not-yet-released) reservations, in file order. Only
    the first `cap` active reservations are granted; a caller that loses the race appends
    a release row for its own reservation and returns False. Releasing a slot frees its
    place for a future reservation — position is computed over active rows only, never
    over the full historical count, so a released slot does not stay burned forever. No
    separate lock file — the append itself is the atomic operation."""
    f = _slot_file(home, run_id); f.parent.mkdir(parents=True, exist_ok=True)
    nonce = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    common.append_jsonl(f, {"fp": fp, "reserved": True, "nonce": nonce, "at": common.utcnow()})
    rows = _read_slots(f)
    released_nonces = {r.get("nonce") for r in rows if r.get("release") is True and r.get("nonce")}
    active_rows = [r for r in rows if r.get("reserved") is True and r.get("nonce") not in released_nonces]
    idx = next((i for i, r in enumerate(active_rows) if r.get("nonce") == nonce), len(active_rows))
    if idx < cap:
        return True
    release_slot(home, run_id, fp, nonce)
    return False

def _latest_nonce_for(home: Path, run_id: str, fp: str) -> str | None:
    rows = _read_slots(_slot_file(home, run_id))
    matches = [r for r in rows if r.get("reserved") is True and r.get("fp") == fp]
    return matches[-1].get("nonce") if matches else None

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
        # NO input can ever traceback the guard: state-JSON loading and the decide() call
        # itself are both inside this one try/except, so any unexpected failure anywhere
        # in the decision path still fails closed with a bad_state deny, never a traceback.
        try:
            state = json.loads(Path(a.state_json).read_text())
            if not isinstance(state, dict):
                raise ValueError("state JSON must be an object")
            out = decide(state, cfg, {"submits_this_run": submits_this_run(home, a.run)}, a.i_mean_it)
        except Exception as e:
            out = {"allow": False, "reason_codes": ["bad_state"], "reasons": [repr(e)]}
            print(json.dumps(out)); sys.exit(3)
        print(json.dumps(out)); sys.exit(0 if out["allow"] else 3)
    if a.cmd == "reserve":
        ok = reserve_slot(home, a.run, a.fp, cfg.get("max_submits_per_run", 5))
        nonce = _latest_nonce_for(home, a.run, a.fp) if ok else None
        print(json.dumps({"reserved": ok, "nonce": nonce})); sys.exit(0 if ok else 3)
    if a.cmd == "release":
        release_slot(home, a.run, a.fp, a.nonce); print("ok")
    if a.cmd == "record":
        record_result(home, a.run, a.fp, a.submitted, a.reason); print("ok")

if __name__ == "__main__":
    main()
