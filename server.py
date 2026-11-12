"""Percy as a service: the pocket gate over HTTP.

Deployable with the standard library only - no dependencies.

    python3 server.py            # PORT env, default 8000
    PERCY_CAP=200.00 python3 server.py

Endpoints:
    GET  /health   -> {"status": "ok", "service": "percy"}
    GET  /         -> small HTML page describing the service
    GET  /demo     -> the fictional $200-cap sequence on a fresh pocket,
                      as JSON: approve, approve, WARN at 85%, BLOCK over
                      the cap, owner raises the cap, retry goes through
                      (WARNED at 88% of the raised cap)
    GET  /state    -> the live pocket: cap, spent, percent used, log size
    POST /pocket   -> the `pocket` tool call as JSON:
                      {"agent_id": "...", "invoice_id": "...",
                       "purpose": "...", "amount": "60.00",
                       "board_checkin_id": "..." (optional)}
                      returns the gate decision; a BLOCKED decision
                      means do not execute the payment.

This service is the gate demo only. It holds no PayPal credentials
and moves no money: the credentialed sandbox flow stays in
sandbox_demo.py, run by the owner with credentials in the
environment only.
"""
import json
import os
import threading
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pocket import PercyPocket

CAP = Decimal(os.getenv("PERCY_CAP", "200.00"))
_lock = threading.Lock()
_pocket = PercyPocket(cap=CAP)

DEMO_AMOUNTS = ["60.00", "70.00", "40.00", "50.00"]


def run_demo():
    """The fictional sequence on a fresh pocket. Mirrors demo.py."""
    pocket = PercyPocket(cap=Decimal("200.00"))
    steps = []
    for i, amount in enumerate(DEMO_AMOUNTS, start=1):
        steps.append(
            pocket.pocket(
                agent_id="agent-board-01",
                invoice_id="INV-00" + str(i),
                amount=amount,
                purpose="supplier invoice",
            )
        )
    steps.append({"owner_action": pocket.raise_cap("250.00")})
    steps.append(
        pocket.pocket(
            agent_id="agent-board-01",
            invoice_id="INV-004",
            amount="50.00",
            purpose="supplier invoice (retry after owner raise)",
        )
    )
    return steps


INDEX_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Percy - the pocket</title></head>
<body>
<h1>Percy - the pocket</h1>
<p>An agent can pay. It cannot splurge. Every payment is checked
against the owner's pocket cap <em>before</em> it goes through:
warn at 80% of cap, block the payment that would pass it.</p>
<ul>
<li><code>GET /demo</code> - the fictional $200-cap sequence as JSON</li>
<li><code>GET /state</code> - the live pocket's cap, meter, percent used</li>
<li><code>POST /pocket</code> - the pocket gate as JSON:
{"agent_id", "invoice_id", "purpose", "amount", "board_checkin_id"?}</li>
<li><code>GET /health</code> - service health</li>
</ul>
<p>Demo service only: sandbox logic, no real money, no credentials held.</p>
</body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, payload):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "service": "percy"})
        elif self.path == "/state":
            with _lock:
                state = {
                    "cap": str(CAP),
                    "spent": str(_pocket.spent),
                    "percent_used": str(_pocket.percent_used),
                    "audit_log_entries": len(_pocket.log),
                }
            self._json(200, state)
        elif self.path == "/demo":
            self._json(200, {"cap": "200.00", "steps": run_demo()})
        elif self.path == "/":
            body = INDEX_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/pocket":
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
            amount = Decimal(str(data["amount"]))
            with _lock:
                result = _pocket.pocket(
                    agent_id=data["agent_id"],
                    invoice_id=data["invoice_id"],
                    purpose=data["purpose"],
                    amount=amount,
                    board_checkin_id=data.get("board_checkin_id"),
                )
            self._json(200, result)
        except (KeyError, ValueError, InvalidOperation, json.JSONDecodeError) as exc:
            self._json(400, {"error": "bad pocket call: " + str(exc)})

    def log_message(self, *args):
        pass


def main():
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("Percy pocket service on port", port, "| cap", str(CAP))
    server.serve_forever()


if __name__ == "__main__":
    main()
