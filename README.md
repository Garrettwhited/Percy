# Percy — the pocket

**PayPal AI Hackathon entry. Sandbox only. No real money.**

An agent can pay. It cannot splurge.

Percy is a pocket: a spend gate that sits in front of a payment.
An agent does not pay directly. It calls `pocket(...)` first.

- Authorize BEFORE any payment goes through.
- WARN at 80% of cap or more.
- BLOCK the payment that would pass the cap, cold. The meter does not move on a blocked attempt. The attempt is logged and the owner is notified.
- Meter reconciled to the cent. Every attempt logged.
- Owner-only cap raise. The agent cannot raise its own cap.
- A pocket call carries `agent_id` and, when there is one, an optional `board_checkin_id`, so spend traces to that check-in. The reference is a reference only.

## Run it

```bash
python3 demo.py
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 sandbox_demo.py
```

Demo, fictional owner and invoices, cap $200/week:
$60 APPROVED, $70 APPROVED, $40 WARNED at $170 / 85%, $50 BLOCKED at $170/$200, owner raises the cap to $250, the blocked invoice then goes through at $220/$250.
36 tests pass.

## Run it as a service (deployable)

**Live hosted demo: https://web-production-9542d44c.up.railway.app** — try `GET /demo`, `GET /state`, or `POST /pocket` against it.

Percy ships deploy-ready: standard library only, no dependencies to install.

```bash
python3 server.py                 # PORT env, default 8000; PERCY_CAP sets the cap
# or: docker build -t percy . && docker run -p 8000:8000 percy
# or: any host that runs the Procfile:  web: python3 server.py
```

- `GET /` — what the service is. `GET /health` — health check.
- `GET /demo` — the fictional $200-cap sequence as JSON.
- `GET /state` — the live pocket: cap, spent, percent used, audit log size.
- `POST /pocket` — the `pocket` gate as JSON: `{"agent_id", "invoice_id", "purpose", "amount", "board_checkin_id"?}` → the gate decision. A BLOCKED decision means do not execute the payment.

The service holds no PayPal credentials and moves no money. The credentialed sandbox flow stays in `sandbox_demo.py`, run by the owner with credentials in the environment only.

## How it is built

- Python, standard library only.
- `pocket.py` — tool call `pocket` (PercyPocket).
- `red_button.py` — cap engine underneath `pocket`.
- `demo.py` — the demo above.
- `server.py` — the pocket gate as an HTTP service (see above), with `Dockerfile` and `Procfile` for deployment.
- `test_pocket.py`, `test_red_button.py`, `test_paypal_pocket.py`, `test_ai_advisor.py`, `test_gate_receipt.py`, `test_server.py` — unit tests.
- `ai_advisor.py` — the AI advisor (see below).
- `paypal_pocket.py` — PayPal Sandbox Orders v2 seam: the pocket gate runs first, a blocked spend never calls PayPal, capture is verified against the gated amount.
- `gate_receipt.py` — binds a capture to the gate decision that authorized it.
- `sandbox_demo.py` — the full flow: advisor → gate → sandbox order → bound capture.

## The AI advisor

Percy's agent proposes; the server disposes.

1. The server builds the eligible list first — only invoices that fit the pocket cap.
2. The AI advisor recommends one invoice from that list. With `ENABLE_AI=1` and a provider key set (env only) — `GEMINI_API_KEY` (Google AI Studio) or `OPENAI_API_KEY`; if both are set, Gemini is used — one bounded model call makes the pick and the run reports mode `AI_MODEL` with the model named. The model cannot invent an invoice or an amount: any pick outside the eligible list is rejected.
3. Without a model configured, a deterministic local rule picks instead and the run reports mode `LOCAL_RULE_AGENT` — no live AI inference is claimed in that mode.
4. Either way, the pocket gate independently authorizes the chosen invoice before PayPal is touched, and the gate receipt binds the later capture to that exact decision: the capture command refuses any order the receipt does not name, verifies the receipt's amount, and uses a per-order idempotency key.

## PayPal Sandbox setup

Sandbox only — this package has no production path.

1. [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/) → Apps & Credentials → **Sandbox** → Create App named **Percy**. PayPal also creates sandbox buyer and seller test accounts under Sandbox → Accounts.
2. Put the app's Client ID and Secret in your environment or secret manager only — never in this repo, a screenshot, or a form. Variable names are in `.env.example`: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`.
3. Run `python3 sandbox_demo.py`. Without credentials it prints BLOCKED and what is missing, and makes no PayPal call. With credentials, the pocket gate decides first, then a sandbox order is created and a sandbox buyer approval link is returned. Open the link, approve as the sandbox buyer, then run `python3 sandbox_demo.py --capture ORDER_ID` — the capture is checked against the gate receipt written at create time (same order, same amount, same currency) before any receipt is accepted.

The agent gets read tools only; money moves only through the `pocket` gate.

## What this is not

- Not a live payment. Sandbox only; no production path.
- No customers, revenue, or results claimed.
- No price or fee set here.

## License

Licensed under the Apache License, Version 2.0. See the LICENSE file in this repo.
Copyright 2026 Garrett Whited.

## Status

Public repository, Nov 11, 2026. Sandbox only.
Deadline for the hackathon: Nov 12, 2026, 2:00 PM CT.
