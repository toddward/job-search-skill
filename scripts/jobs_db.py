#!/usr/bin/env python3
"""JSONL job store: one record per fingerprint, atomic writes, quarantine of bad lines."""
from __future__ import annotations
import json, sys
from pathlib import Path
import common, fingerprint as fpmod

STATUSES = {"new", "shown", "selected", "applied", "not_interested", "expired", "needs_manual_apply"}
KEY_ORDER = ["schema", "fingerprint", "title", "company", "company_key", "title_key", "location", "location_key",
             "remote", "url", "canonical_url", "source", "sources", "posted_at", "closes_at", "comp_min", "comp_max",
             "comp_currency", "comp_basis", "first_seen", "last_seen", "last_shown", "shown_count", "snooze_until",
             "status", "status_changed_at", "status_reason", "fit_score", "fit_breakdown", "fit_reasons",
             "suppressed_by", "content_hash", "version", "application_dir", "applied_at", "submitted",
             "notion_page_id", "notion_synced_at", "run_ids", "description_path", "notes"]
REQUIRED = ["fingerprint", "title", "company", "canonical_url", "source", "first_seen", "last_seen", "status"]

def _ordered(rec: dict) -> dict:
    out = {k: rec[k] for k in KEY_ORDER if k in rec}
    for k, v in rec.items():
        if k not in out:
            out[k] = v
    return out

class JobsDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._rows: dict[str, dict] = {}
        self.load()

    def load(self) -> None:
        self._rows = {}
        bad = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in lines:
            if not line.strip():
                continue
            try:
                r = json.loads(line)
                self._rows[r["fingerprint"]] = r
            except (ValueError, KeyError, TypeError):
                bad.append(line)
        if bad:
            with open(str(self.path).replace(".jsonl", ".badlines.jsonl"), "a", encoding="utf-8") as f:
                f.write("\n".join(bad) + "\n")
            common.atomic_write(self.path, "".join(json.dumps(_ordered(r), ensure_ascii=False, separators=(",", ":")) + "\n"
                                                   for r in self._sorted()))

    def _sorted(self):
        return sorted(self._rows.values(), key=lambda r: (r.get("first_seen", ""), r["fingerprint"]))

    def save(self) -> None:
        common.atomic_write(self.path, "".join(json.dumps(_ordered(r), ensure_ascii=False, separators=(",", ":")) + "\n"
                                               for r in self._sorted()))

    def all(self) -> list[dict]:
        return self._sorted()

    def get(self, fp: str):
        return self._rows.get(fp)

    def find(self, prefix: str):
        if prefix in self._rows:
            return self._rows[prefix]
        if len(prefix) < 6:
            return None
        hits = [r for k, r in self._rows.items() if k.startswith(prefix)]
        return hits[0] if len(hits) == 1 else None

    def by_status(self, status: str) -> list[dict]:
        return [r for r in self._sorted() if r.get("status") == status]

    def upsert(self, rec: dict, now: str | None = None) -> dict:
        now = now or common.utcnow()
        url = rec.get("url") or rec.get("canonical_url") or ""
        remote = rec.get("remote", "")
        fp = rec.get("fingerprint") or fpmod.fingerprint(rec["company"], rec["title"], rec.get("location", ""), remote)
        src = {"source": rec.get("source") or fpmod.detect_source(url), "url": url,
               "canonical_url": fpmod.canonical_url(url), "posting_id": fpmod.posting_id(url),
               "first_seen": now, "last_seen": now}
        cur = self._rows.get(fp)
        if cur is None:
            cur = {"schema": 1, "fingerprint": fp, "title": rec["title"], "company": rec["company"],
                   "company_key": fpmod.company_key(rec["company"]), "title_key": fpmod.title_key(rec["title"]),
                   "location": rec.get("location", ""), "location_key": fpmod.location_key(rec.get("location", ""), remote),
                   "remote": remote or "unknown", "url": url, "canonical_url": src["canonical_url"], "source": src["source"],
                   "sources": [src], "posted_at": rec.get("posted_at"), "closes_at": rec.get("closes_at"),
                   "comp_min": rec.get("comp_min"), "comp_max": rec.get("comp_max"), "comp_currency": rec.get("comp_currency", "USD"),
                   "comp_basis": rec.get("comp_basis"), "first_seen": now, "last_seen": now, "last_shown": None,
                   "shown_count": 0, "snooze_until": None, "status": "new", "status_changed_at": now, "status_reason": None,
                   "fit_score": rec.get("fit_score"), "fit_breakdown": rec.get("fit_breakdown"), "fit_reasons": rec.get("fit_reasons", []),
                   "suppressed_by": None, "content_hash": rec.get("content_hash"), "version": 1, "application_dir": None,
                   "applied_at": None, "submitted": False, "notion_page_id": None, "notion_synced_at": None,
                   "run_ids": list(rec.get("run_ids", [])), "description_path": rec.get("description_path"), "notes": rec.get("notes", "")}
            self._rows[fp] = cur
            return cur
        cur["last_seen"] = now
        existing = next((s for s in cur["sources"] if s["posting_id"] == src["posting_id"]), None)
        if existing:
            existing["last_seen"] = now
        else:
            cur["sources"].append(src)
        best = min(cur["sources"], key=lambda s: (fpmod.canonical_priority(s["canonical_url"]), s["first_seen"]))
        cur["canonical_url"], cur["source"], cur["url"] = best["canonical_url"], best["source"], best["url"]
        old_posted_at = cur.get("posted_at") or ""
        for k in ("posted_at", "closes_at", "comp_min", "comp_max", "comp_basis", "description_path",
                  "fit_score", "fit_breakdown", "fit_reasons", "snooze_until"):
            if rec.get(k) is not None:
                cur[k] = rec[k]
        for rid in rec.get("run_ids", []):
            if rid not in cur["run_ids"]:
                cur["run_ids"].append(rid)
        new_hash = rec.get("content_hash")
        if new_hash and cur.get("content_hash") and new_hash != cur["content_hash"] and \
           (rec.get("posted_at") or "") > old_posted_at:
            cur["version"] = int(cur.get("version", 1)) + 1
            cur["status"], cur["last_shown"], cur["status_changed_at"] = "new", None, now
            cur["status_reason"] = "reposted with material changes"
        if new_hash:
            cur["content_hash"] = new_hash
        return cur

    def set_status(self, fp: str, status: str, reason: str | None = None, now: str | None = None, **extra) -> dict:
        if status not in STATUSES:
            raise ValueError(f"invalid status {status}")
        r = self._rows[fp]
        r["status"], r["status_changed_at"], r["status_reason"] = status, now or common.utcnow(), reason
        r.update(extra)
        return r

    def mark_shown(self, fps: list[str], now: str | None = None) -> None:
        now = now or common.utcnow()
        for fp in fps:
            r = self._rows.get(fp)
            if r is None:
                continue
            r["last_shown"] = now
            r["shown_count"] = int(r.get("shown_count", 0)) + 1
            if r["status"] == "new":
                r["status"], r["status_changed_at"] = "shown", now

    def validate(self) -> list[str]:
        errs = []
        for i, r in enumerate(self._sorted(), 1):
            for k in REQUIRED:
                if k not in r or r[k] in (None, ""):
                    errs.append(f"row {i} ({r.get('fingerprint')}): missing {k}")
            if r.get("status") not in STATUSES:
                errs.append(f"row {i} ({r.get('fingerprint')}): bad status {r.get('status')!r}")
            if r.get("fit_score") is not None and not (0 <= r["fit_score"] <= 100):
                errs.append(f"row {i}: fit_score out of range")
        return errs

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="jobs.jsonl store")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("list"); l.add_argument("--status")
    g = sub.add_parser("get"); g.add_argument("fp")
    u = sub.add_parser("upsert-json"); u.add_argument("file")
    s = sub.add_parser("set-status"); s.add_argument("fp"); s.add_argument("status"); s.add_argument("--reason")
    m = sub.add_parser("mark-shown"); m.add_argument("fps")
    sub.add_parser("validate")
    a = ap.parse_args(argv)
    home = common.data_home(a.home)
    db = JobsDB(home / "memory" / "jobs.jsonl")
    if a.cmd == "list":
        rows = db.by_status(a.status) if a.status else db.all()
        print(json.dumps(rows, ensure_ascii=False))
    elif a.cmd == "get":
        print(json.dumps(db.find(a.fp), ensure_ascii=False))
    elif a.cmd == "upsert-json":
        data = json.loads(Path(a.file).read_text())
        out = [db.upsert(r)["fingerprint"] for r in (data if isinstance(data, list) else [data])]
        db.save(); print(json.dumps(out))
    elif a.cmd == "set-status":
        r = db.find(a.fp)
        if not r:
            sys.exit(f"no job matches {a.fp}")
        db.set_status(r["fingerprint"], a.status, a.reason); db.save(); print(r["fingerprint"])
    elif a.cmd == "mark-shown":
        db.mark_shown([x for x in a.fps.split(",") if x]); db.save(); print("ok")
    elif a.cmd == "validate":
        errs = db.validate(); print("\n".join(errs) or "ok"); sys.exit(1 if errs else 0)

if __name__ == "__main__":
    main()
