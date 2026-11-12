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
16 tests pass.

## How it is built

- Python, standard library only.
- `pocket.py` — tool call `pocket` (PercyPocket).
- `red_button.py` — cap engine underneath `pocket`.
- `demo.py` — the demo above.
- `test_pocket.py`, `test_red_button.py`, `test_paypal_pocket.py` — unit tests.
- `paypal_pocket.py` — PayPal Sandbox Orders v2 seam: the pocket gate runs first, a blocked spend never calls PayPal, capture is verified against the gated amount.
- `sandbox_demo.py` — ready-check and gated sandbox order create.

## PayPal Sandbox setup

Sandbox only — this package has no production path.

1. [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/) → Apps & Credentials → **Sandbox** → Create App named **Percy**. PayPal also creates sandbox buyer and seller test accounts under Sandbox → Accounts.
2. Put the app's Client ID and Secret in your environment or secret manager only — never in this repo, a screenshot, or a form. Variable names are in `.env.example`: `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`.
3. Run `python3 sandbox_demo.py`. Without credentials it prints BLOCKED and what is missing, and makes no PayPal call. With credentials, the pocket gate decides first, then a sandbox order is created and a sandbox buyer approval link is returned. Open the link, approve as the sandbox buyer, then run `python3 sandbox_demo.py --capture ORDER_ID` — the capture is verified against the gated amount and currency before any receipt is accepted.

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
