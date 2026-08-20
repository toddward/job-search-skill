#!/usr/bin/env python3
"""Shared helpers for the job-search skill scripts. Stdlib only."""
from __future__ import annotations
import hashlib, json, os, platform, re, tempfile
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_HOME = Path.home() / "job-search"

def pointer_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", "")
    base = Path(xdg) if xdg and os.path.isabs(xdg) else Path.home() / ".config"
    return base / "job-search" / "home"

POINTER = pointer_path()
DATA_SUBDIRS = ["resume", "config", "memory", "memory/jd", "memory/logs", "memory/runs",
                "memory/ats-learned", "reports", "applications"]

def data_home_info(override: str | None = None) -> tuple[Path, str]:
    """Resolve the data home and how it was chosen: cli | env | pointer | default."""
    if override:
        return Path(override).expanduser().resolve(), "cli"
    env = os.environ.get("JOBSEARCH_HOME")
    if env:
        return Path(env).expanduser().resolve(), "env"
    try:
        txt = POINTER.read_text().strip()
        if txt:
            return Path(txt).expanduser().resolve(), "pointer"
    except OSError:
        pass
    return DEFAULT_HOME, "default"

def data_home(override: str | None = None) -> Path:
    return data_home_info(override)[0]

def ensure_dirs(home: Path) -> None:
    for d in DATA_SUBDIRS:
        (home / d).mkdir(parents=True, exist_ok=True)

def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_ts(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def days_between(a: str, b: str) -> float:
    return (parse_ts(b) - parse_ts(a)).total_seconds() / 86400.0

def sha16(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:maxlen].rstrip("-")

def host_os() -> str:
    sysname = platform.system()
    return {"Darwin": "macos", "Linux": "linux"}.get(sysname, "other")

def atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default

def write_json(path: Path, obj) -> None:
    atomic_write(Path(path), json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

def read_jsonl(path: Path) -> list[dict]:
    out = []
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    except OSError:
        pass
    return out

def append_jsonl(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n")
