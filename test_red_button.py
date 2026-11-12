import unittest
from decimal import Decimal

from red_button import RedButton


class TestRedButton(unittest.TestCase):
    def test_approve_below_80(self):
        rb = RedButton(cap=Decimal("200.00"))
        a = rb.authorize("INV-1", "60.00")
        self.assertEqual(a.decision, "APPROVED")
        self.assertEqual(rb.spent, Decimal("60.00"))

    def test_warn_at_80(self):
        rb = RedButton(cap=Decimal("200.00"))
        rb.authorize("INV-1", "100.00")
        a = rb.authorize("INV-2", "60.00")  # $160 = 80%
        self.assertEqual(a.decision, "WARNED")

    def test_block_passing_call_and_meter_unchanged(self):
        rb = RedButton(cap=Decimal("200.00"))
        rb.authorize("INV-1", "170.00")
        a = rb.authorize("INV-2", "50.00")
        self.assertEqual(a.decision, "BLOCKED")
        self.assertEqual(rb.spent, Decimal("170.00"))

    def test_exact_cap_approved_not_blocked(self):
        rb = RedButton(cap=Decimal("200.00"))
        rb.authorize("INV-1", "170.00")
        a = rb.authorize("INV-2", "30.00")
        self.assertEqual(a.decision, "WARNED")  # 100%, warned, not blocked
        self.assertEqual(rb.spent, Decimal("200.00"))

    def test_owner_raise_then_retry_passes(self):
        rb = RedButton(cap=Decimal("200.00"))
        rb.authorize("INV-1", "170.00")
        self.assertEqual(rb.authorize("INV-2", "50.00").decision, "BLOCKED")
        rb.raise_cap(Decimal("250.00"), by="owner")
        self.assertEqual(rb.authorize("INV-2", "50.00").decision, "WARNED")

    def test_agent_cannot_raise_cap(self):
        rb = RedButton(cap=Decimal("200.00"))
        with self.assertRaises(PermissionError):
            rb.raise_cap(Decimal("999.00"), by="agent")


if __name__ == "__main__":
    unittest.main()
