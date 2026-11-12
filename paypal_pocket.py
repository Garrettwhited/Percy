"""Percy + PayPal Sandbox: the pocket gate runs BEFORE any PayPal call.

Sandbox only. Base URL is the PayPal sandbox API host; there is no
production path in this file. Credentials come from the environment
only (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET) and are never printed,
logged, or stored. Standard library only.

Flow:
  1. pocket(...) authorizes the spend against the cap (approve / warn /
     block). A blocked spend never reaches PayPal.
  2. Orders v2 create_order, intent CAPTURE, with an idempotency key.
  3. The buyer approves on the returned sandbox approval link.
  4. capture_order verifies status COMPLETED and that the captured
     amount and currency match the gated amount exactly.
"""
import base64
import json
import os
import urllib.parse
import urllib.request
from decimal import Decimal

from pocket import PercyPocket  # noqa: F401  (re-exported for callers)

BASE = "https://api-m.sandbox.paypal.com"
APPROVAL_HOSTS = ("www.sandbox.paypal.com", "sandbox.paypal.com")


class PayPalPocketError(Exception):
    pass


class PayPalSandbox:
    """Minimal Orders v2 sandbox client. Transport is injectable for tests."""

    def __init__(self, client_id=None, client_secret=None, transport=None):
        self.client_id = client_id or os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("PAYPAL_CLIENT_SECRET")
        self.transport = transport or self._urlopen
        if not self.client_id or not self.client_secret:
            raise PayPalPocketError(
                "PayPal sandbox credentials missing: set PAYPAL_CLIENT_ID "
                "and PAYPAL_CLIENT_SECRET in the environment."
            )

    @staticmethod
    def _urlopen(request):
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    def _token(self):
        auth = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        req = urllib.request.Request(
            BASE + "/v1/oauth2/token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": "Basic " + auth,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        return self.transport(req)["access_token"]

    def _post(self, path, token, body, request_id):
        if not request_id or len(request_id) > 64:
            raise PayPalPocketError("Invalid idempotency ID")
        req = urllib.request.Request(
            BASE + path,
            data=json.dumps(body).encode() if body is not None else b"",
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "PayPal-Request-Id": request_id,
            },
            method="POST",
        )
        return self.transport(req)

    def create_order(self, cents_amount, request_id):
        if cents_amount <= 0:
            raise PayPalPocketError("Invalid order amount")
        token = self._token()
        amt = f"{cents_amount // 100}.{cents_amount % 100:02d}"
        data = self._post(
            "/v2/checkout/orders",
            token,
            {
                "intent": "CAPTURE",
                "purchase_units": [
                    {"amount": {"currency_code": "USD", "value": amt}}
                ],
            },
            "create-" + request_id[:57],
        )
        if not data.get("id") or data.get("status") not in (
            "CREATED",
            "PAYER_ACTION_REQUIRED",
            "SAVED",
            "APPROVED",
        ):
            raise PayPalPocketError("PayPal create response not verified")
        approve = next(
            (
                link["href"]
                for link in data.get("links", [])
                if link.get("rel") in ("approve", "payer-action")
            ),
            None,
        )
        if not approve:
            raise PayPalPocketError("PayPal approval step missing")
        parsed = urllib.parse.urlsplit(approve)
        if parsed.scheme != "https" or parsed.hostname not in APPROVAL_HOSTS:
            raise PayPalPocketError("Unsafe PayPal approval URL")
        return {"order_id": data["id"], "approve_url": approve, "status": data["status"]}

    def capture_order(self, order_id, expected_cents, request_id):
        allowed = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        )
        if not order_id or any(ch not in allowed for ch in order_id):
            raise PayPalPocketError("Invalid PayPal order ID")
        token = self._token()
        data = self._post(
            f"/v2/checkout/orders/{order_id}/capture",
            token,
            None,
            "capture-" + request_id[:56],
        )
        if data.get("status") != "COMPLETED":
            raise PayPalPocketError("PayPal capture not completed")
        units = data.get("purchase_units") or []
        captures = [
            cap
            for unit in units
            for cap in (unit.get("payments") or {}).get("captures", [])
        ]
        if len(captures) != 1:
            raise PayPalPocketError("PayPal capture receipt is incomplete")
        cap = captures[0]
        amount = cap.get("amount") or {}
        if amount.get("currency_code") != "USD":
            raise PayPalPocketError("Capture currency mismatch")
        raw = Decimal(str(amount.get("value"))) * 100
        if not raw.is_finite() or raw != raw.to_integral_value():
            raise PayPalPocketError("Invalid capture amount precision")
        if int(raw) != expected_cents:
            raise PayPalPocketError("Capture amount does not match gated amount")
        return {
            "capture_id": cap.get("id"),
            "order_id": order_id,
            "status": data["status"],
            "amount_cents": int(raw),
            "currency": "USD",
            "create_time": cap.get("create_time"),
        }


def gated_create_order(pocket: PercyPocket, paypal: PayPalSandbox, *,
                       agent_id, purpose, invoice_id, amount,
                       board_checkin_id=None, request_id):
    """Authorize through the pocket first; only then touch PayPal.

    Returns (gate_result, order_or_None). On a block, order is None and
    PayPal is never called.
    """
    result = pocket.pocket(
        agent_id=agent_id,
        purpose=purpose,
        invoice_id=invoice_id,
        amount=amount,
        board_checkin_id=board_checkin_id,
    )
    if not result["execute_payment"]:
        return result, None
    cents = int(Decimal(str(amount)) * 100)
    order = paypal.create_order(cents, request_id)
    return result, order
