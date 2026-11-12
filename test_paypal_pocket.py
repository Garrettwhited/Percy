import unittest

from decimal import Decimal

from pocket import PercyPocket
from paypal_pocket import PayPalSandbox, gated_create_order


class FakeTransport:
    """Records every request; returns canned PayPal sandbox responses."""

    def __init__(self):
        self.paths = []

    def __call__(self, request):
        url = request.full_url
        self.paths.append(url)
        if url.endswith("/v1/oauth2/token"):
            return {"access_token": "test-token"}
        if url.endswith("/v2/checkout/orders"):
            return {
                "id": "ORDER123",
                "status": "CREATED",
                "links": [
                    {
                        "rel": "approve",
                        "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123",
                    }
                ],
            }
        if url.endswith("/v2/checkout/orders/ORDER123/capture"):
            return {
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [
                                {
                                    "id": "CAPTURE123",
                                    "amount": {"currency_code": "USD", "value": "60.00"},
                                    "create_time": "2026-11-11T00:00:00Z",
                                }
                            ]
                        }
                    }
                ],
            }
        raise AssertionError("unexpected URL " + url)


def make_paypal(transport):
    return PayPalSandbox(client_id="cid", client_secret="secret", transport=transport)


class TestGatedFlow(unittest.TestCase):
    def test_blocked_spend_never_calls_paypal(self):
        transport = FakeTransport()
        paypal = make_paypal(transport)
        pocket = PercyPocket(cap=Decimal("100"))
        result, order = gated_create_order(
            pocket, paypal,
            agent_id="agent-1", purpose="supplier", invoice_id="INV-9",
            amount=150, request_id="req-block-1",
        )
        self.assertFalse(result["execute_payment"])
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertIsNone(order)
        self.assertEqual(transport.paths, [])  # PayPal untouched on a block

    def test_approved_spend_creates_order(self):
        transport = FakeTransport()
        paypal = make_paypal(transport)
        pocket = PercyPocket(cap=Decimal("200"))
        result, order = gated_create_order(
            pocket, paypal,
            agent_id="agent-1", purpose="supplier", invoice_id="INV-1",
            amount=60, request_id="req-ok-1",
        )
        self.assertTrue(result["execute_payment"])
        self.assertEqual(order["order_id"], "ORDER123")
        self.assertIn("sandbox.paypal.com", order["approve_url"])

    def test_capture_verifies_amount_and_status(self):
        transport = FakeTransport()
        paypal = make_paypal(transport)
        receipt = paypal.capture_order("ORDER123", 6000, "req-cap-1")
        self.assertEqual(receipt["capture_id"], "CAPTURE123")
        self.assertEqual(receipt["amount_cents"], 6000)
        self.assertEqual(receipt["status"], "COMPLETED")

    def test_capture_amount_mismatch_rejected(self):
        transport = FakeTransport()
        paypal = make_paypal(transport)
        with self.assertRaises(Exception):
            paypal.capture_order("ORDER123", 5000, "req-cap-2")

    def test_missing_credentials_fail_closed(self):
        with self.assertRaises(Exception):
            PayPalSandbox(client_id="", client_secret="", transport=FakeTransport())


if __name__ == "__main__":
    unittest.main()
