import json
import os
import tempfile
import unittest
from decimal import Decimal

from gate_receipt import capture_request_id, load_receipt, verify_binding, write_receipt
from pocket import PercyPocket
from paypal_pocket import PayPalSandbox, gated_create_order


class FakeTransport:
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
                "links": [{
                    "rel": "approve",
                    "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123",
                }],
            }
        if url.endswith("/v2/checkout/orders/ORDER123/capture"):
            return {
                "status": "COMPLETED",
                "purchase_units": [{"payments": {"captures": [{
                    "id": "CAPTURE123",
                    "amount": {"currency_code": "USD", "value": "60.00"},
                    "create_time": "2026-11-11T00:00:00Z",
                }]}}],
            }
        raise AssertionError("unexpected URL " + url)


class TestGateReceiptBinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "receipt.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _create_and_write_receipt(self):
        transport = FakeTransport()
        paypal = PayPalSandbox(client_id="cid", client_secret="s", transport=transport)
        pocket = PercyPocket(cap=Decimal("200"))
        result, order = gated_create_order(
            pocket, paypal,
            agent_id="agent-board-01", purpose="supplier invoice",
            invoice_id="INV-001", amount="60.00", request_id="percy-INV-001",
        )
        receipt = write_receipt(
            self.path, order_id=order["order_id"], gate_result=result,
            amount_cents=6000, create_request_id="percy-INV-001",
        )
        return transport, paypal, receipt

    def test_receipt_binds_order_invoice_decision(self):
        _, _, receipt = self._create_and_write_receipt()
        self.assertEqual(receipt["order_id"], "ORDER123")
        self.assertEqual(receipt["invoice_id"], "INV-001")
        self.assertEqual(receipt["decision"], "APPROVED")
        self.assertEqual(receipt["amount_cents"], 6000)
        loaded = load_receipt(self.path)
        self.assertEqual(loaded["order_id"], "ORDER123")

    def test_capture_idempotency_key_is_per_order(self):
        self.assertEqual(capture_request_id("ORDER123"), "capture-ORDER123")
        self.assertNotEqual(capture_request_id("ORDER123"), capture_request_id("ORDER999"))

    def test_wrong_order_capture_refused(self):
        self._create_and_write_receipt()
        receipt = load_receipt(self.path)
        with self.assertRaises(ValueError):
            verify_binding(receipt, "ORDER999")

    def test_bound_capture_verifies_against_receipt_amount(self):
        _, paypal, _ = self._create_and_write_receipt()
        receipt = load_receipt(self.path)
        amount = verify_binding(receipt, "ORDER123")
        captured = paypal.capture_order("ORDER123", amount, "ORDER123")
        self.assertEqual(captured["capture_id"], "CAPTURE123")
        self.assertEqual(captured["amount_cents"], 6000)

    def test_blocked_decision_cannot_write_receipt(self):
        gate_result = {
            "invoice_id": "INV-9", "agent_id": "a", "board_checkin_id": None,
            "decision": "BLOCKED", "percent_used": "85.00", "cap": "200",
        }
        with self.assertRaises(ValueError):
            write_receipt(self.path, order_id="X", gate_result=gate_result,
                          amount_cents=100, create_request_id="r")
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
