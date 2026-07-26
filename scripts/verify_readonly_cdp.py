#!/usr/bin/env python3
"""F2 — the LIVE-BROWSER proof that the read-only CDP surface is read-only.

`eval/tests/test_cdp_readonly_surface.py` proves the structure and the refusals without a browser,
because the clean-clone gate installs declared dependencies into a fresh venv and has no Chrome —
and a guard that must be skipped there is silence, not a pass. This script is the other half: it
drives `ReadOnlyCdpObserver` against a real headless Chrome showing the repository's OWN mock TMS
site, confirms real observation works, and confirms the hostile attempts are refused against a real
browser rather than a fake transport.

It is an EVIDENCE PRODUCER, not part of the canonical suite. Run it when the read surface changes:

    .venv/bin/python scripts/verify_readonly_cdp.py [--chrome /path/to/chrome]

Exit status 0 means every check passed. The JSON it prints is the evidence.

It performs NO external writes: the only browser it touches is one it launches itself, in a
throwaway profile, pointed at a local file server serving a generated mock site.
"""

from __future__ import annotations

import argparse
import http.server
import json
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

DEFAULT_CORPUS = ROOT / "data" / "synthetic_corpus"
_CHROME_GLOBS = (
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "~/Library/Caches/ms-playwright/chromium-*/chrome-mac/"
    "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "~/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
)


def find_chrome(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit).expanduser()
        return p if p.exists() else None
    for pattern in _CHROME_GLOBS:
        expanded = Path(pattern).expanduser()
        matches = sorted(Path(expanded.anchor).glob(str(expanded.relative_to(expanded.anchor))))
        if matches:
            return matches[-1]
    for name in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chrome", default=None, help="path to a Chrome/Chromium binary")
    ap.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    args = ap.parse_args()

    chrome = find_chrome(args.chrome)
    if chrome is None:
        print(json.dumps({"error": "no Chrome/Chromium found; pass --chrome"}, indent=2))
        return 2

    from freight_recon.cdp_readonly import ReadOnlyCdpError, ReadOnlyCdpObserver
    from freight_recon.mock_tms import build_mock_tms_site
    from run_workflow import load_synthetic_loads

    tmp = Path(tempfile.mkdtemp(prefix="ro-cdp-"))
    profile = tempfile.mkdtemp(prefix="ro-prof-")
    site = tmp / "site"
    checks: dict[str, object] = {}
    failures: list[str] = []

    def check(name: str, ok: bool, detail: object = "") -> None:
        checks[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            failures.append(name)

    try:
        corpus = Path(args.corpus)
        build_mock_tms_site(
            output_dir=site, corpus_dir=corpus,
            loads=load_synthetic_loads(corpus)[:6], store=None,
        )
        page = "payables.html" if (site / "payables.html").exists() else "index.html"

        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(  # noqa: E731
            *a, directory=str(site), **k
        )
        httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{httpd.server_address[1]}/{page}"
        cdp_port = free_port()

        proc = subprocess.Popen(
            [str(chrome), "--headless=new", f"--remote-debugging-port={cdp_port}",
             f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check", url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            attached = False
            for _ in range(240):
                try:
                    targets = json.load(
                        urllib.request.urlopen(f"http://localhost:{cdp_port}/json", timeout=2)
                    )
                    if any(t.get("type") == "page" and t.get("webSocketDebuggerUrl")
                           for t in targets):
                        attached = True
                        break
                except (urllib.error.URLError, OSError, ValueError):
                    pass
                time.sleep(0.5)
            check("chrome_page_target_available", attached, str(chrome))
            if not attached:
                raise RuntimeError("no page target appeared")

            with ReadOnlyCdpObserver(
                cdp_url=f"http://localhost:{cdp_port}", url_filter="127.0.0.1"
            ) as obs:
                observation = obs.observe()
                check("observe_returns_structured_page", isinstance(observation, dict)
                      and bool(observation.get("body_text")),
                      {"keys": sorted(observation) if isinstance(observation, dict) else None,
                       "tables": len(observation.get("tables") or []),
                       "body_text_len": len(observation.get("body_text") or "")})
                check("current_url_is_the_mock_tms", obs.current_url().endswith(page),
                      obs.current_url())
                check("page_signature_reports_complete",
                      obs.page_signature().startswith("complete|"), obs.page_signature()[:70])
                check("read_returns_a_string", isinstance(obs.read("total"), str))
                check("is_submit_target_returns_a_bool",
                      isinstance(obs.is_submit_target("Save"), bool))
                shot = Path(obs.capture_screenshot(tmp / "shot.png"))
                check("screenshot_written", shot.stat().st_size > 1000, shot.stat().st_size)

                # -- hostile, against a REAL browser --------------------------------------
                private = getattr(obs, "_ReadOnlyCdpObserver__channel")
                refused = {}
                for method, params in (
                    ("Runtime.evaluate", {"expression": "document.title='pwned'"}),
                    ("Input.insertText", {"text": "999999"}),
                    ("Input.dispatchMouseEvent", {"type": "mousePressed"}),
                    ("DOM.setFileInputFiles", {"files": ["/etc/hosts"]}),
                    ("Page.navigate", {"url": "https://example.com"}),
                ):
                    try:
                        private.send(method, params)
                        refused[method] = False
                    except ReadOnlyCdpError:
                        refused[method] = True
                check("every_actuation_method_refused", all(refused.values()), refused)

                try:
                    private.send("Runtime.callFunctionOn", {
                        "functionDeclaration": "function(){document.title='pwned';return 1;}"})
                    unvetted_refused = False
                except ReadOnlyCdpError:
                    unvetted_refused = True
                check("unvetted_script_refused", unvetted_refused)

                after = obs.observe()
                check("page_unchanged_by_hostile_attempts",
                      after.get("url") == observation.get("url")
                      and "pwned" not in json.dumps(after))
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
            httpd.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(profile, ignore_errors=True)

    print(json.dumps({"checks": checks, "failures": failures,
                      "verdict": "PASS" if not failures else "FAIL"}, indent=2, default=str))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
