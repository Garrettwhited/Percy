# Percy — Tokenized Wallet Grants (sandbox prototype)

**Status: SANDBOX ONLY. Not deployed, not production-ready, no real funds, no PayPal wallet or card token.**

## Intended user experience

1. Issuer chooses a verified recipient, purpose whitelist, USD spending allowance, and expiration.
2. Percy creates a strong single-use invitation token. A secure delivery service sends it to the intended recipient (delivery is **not implemented** here).
3. Recipient signs in. A **trusted host identity verifier** (not a user-controlled text field) matches the authenticated subject to the recipient on the invitation.
4. Invitation is exchanged for a distinct access token. Both tokens are stored in memory **only as SHA-256 hashes**.
5. Each spending request rechecks identity, expiration, scope and revocation; **PercyPocket** makes the actual allowance decision.
6. Issuer can revoke access. The prototype returns gate outcomes but **does not create or capture PayPal orders**.

Example: issue a USD $250 / seven-day grant for "supplier invoices". An authenticated recipient claims it, requests $60, and gets a Percy APPROVED gate decision. A $300 attempt is BLOCKED without increasing the meter. This is **not** an actual $60 transfer.

## API (Python class; not HTTP)

- `TokenizedWallets(issuer_secret=..., verify_recipient=...)`
- `issue(issuer_secret=..., recipient=..., cap=..., purposes=..., ttl_seconds=...)`
- `claim(invitation_token=..., identity_proof=...)`
- `authorize(access_token=..., identity_proof=..., agent_id=..., invoice_id=..., amount=..., purpose=...)`
- `revoke(issuer_secret=..., wallet_id=...)`
- `status(issuer_secret=..., wallet_id=...)`

A missing verifier refuses claims. The sample proof-to-identity mapping in tests is **test-only**, not a real authentication implementation.

## Verification

Run `python3 -m unittest -v test_tokenized_wallet.py` and the existing Percy tests. The new tests exercise 16 sandbox scenarios. Local isolated prototype tests passed, but repository CI and complete integration acceptance are **not yet established**.

## Production blockers — promotion forbidden until resolved

- Strong issuer authentication and independently verified recipient sessions, authorization, secure issuance/delivery, token rotation and recovery.
- Durable transactional persistence and cross-process locking, replay protections and event audit retention.
- Record a prepayment **reservation**, not final spend; reconcile to PayPal order/capture/refund/void webhook receipts, with failure and retry handling. Do not accidentally double-debit.
- Identify the actual permitted PayPal merchant, payer and checkout/authorization flows for this product; validate current PayPal policies and financial/regulatory implications. Do not represent grants as PayPal vaulted payment-method tokens or money balances.
- Complete adversarial tests (token leakage, CSRF, rate limits, forged identity, concurrent requests, transport security, error handling, outage and recovery).
- Owner approval and evidence-gated integration with `paypal_pocket.py`. **Do not add endpoints to the existing unauthenticated public demo service.**
- Required system control-plane verification and deployment rollback plan before any environment promotion.

No payment credentials, live endpoints, money transfer or production deployment are part of this change.
