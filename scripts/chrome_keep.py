#!/usr/bin/env python3
"""Keep the headed apply Chrome alive after fill.

Playwright must attach over CDP to a Chrome that outlives the fill process.
`launch_persistent_context` as a child of the fill script dies when the script
exits — that is the bug this module exists to prevent.
"""
from __future__ import annotations
import json, socket, subprocess, sys, time
from pathlib import Path
from urllib.parse import urlparse
import common, html2pdf

DEFAULT_PORT = 9223


def endpoint_url(port: int) -> str:
    return f"http://127.0.0.1:{int(port)}"


def port_from_endpoint(url: str) -> int | None:
    if not (url or "").strip():
        return None
    u = urlparse(url.strip())
    if u.port:
        return int(u.port)
    if u.scheme in ("http", "ws"):
        return 80
    if u.scheme in ("https", "wss"):
        return 443
    return None


def is_listening(host: str, port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.3)
    try:
        s.connect((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        s.close()


def chrome_launch_args(chrome_bin: str, profile: Path, port: int) -> list[str]:
    profile = Path(profile).expanduser().resolve()
    return [
        str(chrome_bin),
        f"--remote-debugging-port={int(port)}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-session-crashed-bubble",
        "--new-window",
        "about:blank",
    ]


def popen_kwargs() -> dict:
    # Detach from the fill script's process group so a wrapper timeout/SIGTERM
    # cannot take Chrome down with it.
    return {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "start_new_session": True}


def ensure_debug_chrome(profile: Path, *, chrome_bin: str | None = None, endpoint: str = "",
                        port: int = DEFAULT_PORT, headed: bool = True, timeout_s: float = 10.0) -> dict:
    """Return `{endpoint, launched, pid}`. Never closes the browser."""
    if not headed:
        raise RuntimeError("chrome_keep is headed-only; headless fill must not keep a window")
    if endpoint:
        p = port_from_endpoint(endpoint) or port
        host = urlparse(endpoint).hostname or "127.0.0.1"
        if is_listening(host, p):
            return {"endpoint": endpoint, "launched": False, "pid": None}
        port = p
    if is_listening("127.0.0.1", port):
        return {"endpoint": endpoint_url(port), "launched": False, "pid": None}
    bin_ = chrome_bin or html2pdf.find_browser("auto")
    if not bin_:
        raise RuntimeError("no Chrome/Chromium found; install Google Chrome or set output.chrome_path")
    Path(profile).mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(chrome_launch_args(bin_, Path(profile), port), **popen_kwargs())
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if is_listening("127.0.0.1", port):
            return {"endpoint": endpoint_url(port), "launched": True, "pid": proc.pid}
        time.sleep(0.2)
    raise RuntimeError(f"Chrome did not open debug port {port}")


def main(argv=None):
    import argparse, config
    ap = argparse.ArgumentParser(description="headed apply Chrome that outlives the fill process")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    en = sub.add_parser("ensure")
    en.add_argument("--port", type=int)
    a = ap.parse_args(argv)
    home = common.data_home(a.home)
    cfg = config.load(home)
    if cfg["apply"].get("browser_mode") == "headless":
        print("chrome_keep is headed-only", file=sys.stderr)
        sys.exit(2)
    profile = config.resolve_path(cfg, "apply.browser_profile_path")
    endpoint = (cfg["apply"].get("cdp_endpoint") or "").strip()
    port = a.port if a.cmd == "ensure" and a.port else (port_from_endpoint(endpoint) or DEFAULT_PORT)
    chrome = html2pdf.find_browser(cfg["output"].get("chrome_path") or "auto")
    out = ensure_debug_chrome(profile, chrome_bin=chrome, endpoint=endpoint, port=port, headed=True)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
