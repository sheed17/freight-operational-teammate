"""A *writable* mock TMS web surface for browser-use execution drills.

The read-only mock TMS (``generate_mock_tms.py``) serves static load pages. This adds the one screen
the execution agent must operate for real: a **carrier-payable entry form** plus a **payables
readback table**. browser-use types the human-approved amount into the form and clicks Submit, then
reads the amount back from the table — exactly the confirm-and-verify a human does in a real TMS.

The server is deliberately thin and owns no money logic of its own: every write delegates to the
already-tested :class:`~freight_recon.tms_write.MockTmsWriteLedger`, so idempotency, duplicate
blocking, and the persisted ledger are the same proven code the JSON path uses. This module only
renders HTML and routes requests; it never decides an amount.
"""

from __future__ import annotations

import argparse
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .tms_write import MockTmsWriteLedger


def render_payable_form(*, load_id: str, run_id: str, carrier: str, key: str) -> str:
    """The entry screen the agent operates: carrier/run/key are pre-filled; the agent types amount."""
    esc = html.escape
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Enter Carrier Payable</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:40px auto">
<h1>Carrier Payable Entry</h1>
<p>Load <b id="load_id">{esc(load_id)}</b> &middot; Carrier <b>{esc(carrier)}</b></p>
<form id="payable-form" method="POST" action="/payables">
  <input type="hidden" name="load_id" value="{esc(load_id)}">
  <input type="hidden" name="run_id" value="{esc(run_id)}">
  <input type="hidden" name="carrier" value="{esc(carrier)}">
  <input type="hidden" name="idempotency_key" value="{esc(key)}">
  <p>
    <label for="amount" style="display:block;font-weight:bold;margin-bottom:6px">Approved amount (USD)</label>
    <input type="text" id="amount" name="amount" value="" placeholder="0.00" autofocus
           style="font-size:20px;padding:8px;width:200px">
  </p>
  <button id="submit-payable" type="submit" style="font-size:18px;padding:10px 24px">Enter payable</button>
</form>
</body></html>"""


def render_confirmation(result) -> str:
    esc = html.escape
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Payable {esc(result.status.value)}</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:40px auto">
<h1>Payable submission result</h1>
<p style="font-size:22px">Status: <strong id="write-status">{esc(result.status.value)}</strong></p>
<p style="font-size:18px">Reference: <strong id="external-ref">{esc(result.external_ref or '')}</strong></p>
<p>Load <span id="load_id">{esc(result.load_id)}</span> &middot; key <span id="idempotency-key">{esc(result.idempotency_key)}</span></p>
<p id="note">{esc(result.note)}</p>
<p><a href="/payables.html">Back to payables</a></p>
</body></html>"""


def render_payables_table(ledger: MockTmsWriteLedger) -> str:
    data = ledger._read()  # noqa: SLF001 - intentional: render the ledger's persisted rows
    rows = []
    for load_id, rec in sorted(data.items()):
        rows.append(
            f'<tr class="payable-row" data-load-id="{html.escape(load_id)}">'
            f'<td class="load-id">{html.escape(load_id)}</td>'
            f'<td class="carrier">{html.escape(str(rec.get("carrier","")))}</td>'
            f'<td class="amount">{html.escape(str(rec.get("amount","")))}</td>'
            f'<td class="external-ref">{html.escape(str(rec.get("external_ref","")))}</td>'
            f'<td class="idempotency-key">{html.escape(str(rec.get("idempotency_key","")))}</td>'
            f"</tr>"
        )
    body = "\n".join(rows) or '<tr><td colspan="5">No payables entered yet.</td></tr>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Carrier Payables</title></head>
<body>
<h1>Carrier Payables</h1>
<table id="payables">
<tr><th>Load</th><th>Carrier</th><th>Amount</th><th>Reference</th><th>Key</th></tr>
{body}
</table>
</body></html>"""


def make_handler(*, site_dir: Path, ledger: MockTmsWriteLedger):
    class WritableTmsHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            return

        def _send(self, body: str, status: int = 200) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/payables.html", "/tms/payables.html"):
                self._send(render_payables_table(ledger))
                return
            if path in ("/payables/new", "/tms/payables/new"):
                q = parse_qs(parsed.query)
                self._send(
                    render_payable_form(
                        load_id=(q.get("load_id") or [""])[0],
                        run_id=(q.get("run_id") or [""])[0],
                        carrier=(q.get("carrier") or [""])[0],
                        key=(q.get("key") or [""])[0],
                    )
                )
                return
            # static load pages from the generated read-only site
            rel = path.lstrip("/").removeprefix("tms/")
            target = (site_dir / rel).resolve()
            if site_dir.resolve() in target.parents and target.is_file():
                self._send(target.read_text(encoding="utf-8"))
                return
            self._send("<h1>404</h1>", status=404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path not in ("/payables", "/tms/payables"):
                self._send("<h1>404</h1>", status=404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            get = lambda k: (form.get(k) or [""])[0]  # noqa: E731
            try:
                run_id = int(get("run_id") or "0")
            except ValueError:
                run_id = 0
            result = ledger.write_payable(
                run_id=run_id,
                load_id=get("load_id"),
                carrier=get("carrier"),
                amount=get("amount").strip(),
                charges=[],
                key=get("idempotency_key"),
            )
            self._send(render_confirmation(result))

    return WritableTmsHandler


def serve(*, site_dir: Path, ledger_path: Path, host: str = "127.0.0.1", port: int = 8012) -> None:
    ledger = MockTmsWriteLedger(ledger_path)
    handler = make_handler(site_dir=site_dir, ledger=ledger)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Writable mock TMS on http://{host}:{port}  (ledger: {ledger_path})")
    print(f"  form:     http://{host}:{port}/payables/new?load_id=LD-560004&run_id=2&carrier=Great+Lakes+Drayage+Co&key=<key>")
    print(f"  readback: http://{host}:{port}/payables.html")
    server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve the writable mock TMS for browser-use execution.")
    parser.add_argument("--site", required=True, help="Generated read-only mock TMS dir (load pages)")
    parser.add_argument("--ledger", required=True, help="JSON payable ledger path (the TMS write target)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args()
    serve(site_dir=Path(args.site), ledger_path=Path(args.ledger), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
