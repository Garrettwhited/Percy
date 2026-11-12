import unittest
from decimal import Decimal

from pocket import PercyPocket


class TestPocket(unittest.TestCase):
    def test_pocket_approves_and_carries_board_checkin(self):
        pocket = PercyPocket(cap=Decimal("200.00"))
        out = pocket.pocket(
            agent_id="agent-board-01",
            invoice_id="INV-1",
            amount="60.00",
            purpose="supplier invoice",
            board_checkin_id="CHECKIN-001",
        )
        self.assertEqual(out["decision"], "APPROVED")
        self.assertTrue(out["execute_payment"])
        self.assertEqual(out["board_checkin_id"], "CHECKIN-001")
        self.assertEqual(out["agent_id"], "agent-board-01")
        self.assertEqual(pocket.spent, Decimal("60.00"))

    def test_pocket_warns_at_80(self):
        pocket = PercyPocket(cap=Decimal("200.00"))
        pocket.pocket("agent-board-01", "INV-1", "100.00", "supplier invoice")
        out = pocket.pocket("agent-board-01", "INV-2", "60.00", "supplier invoice")
        self.assertEqual(out["decision"], "WARNED")
        self.assertTrue(out["execute_payment"])

    def test_pocket_blocks_passing_call_and_does_not_execute(self):
        pocket = PercyPocket(cap=Decimal("200.00"))
        pocket.pocket("agent-board-01", "INV-1", "170.00", "supplier invoice")
        out = pocket.pocket("agent-board-01", "INV-2", "50.00", "supplier invoice")
        self.assertEqual(out["decision"], "BLOCKED")
        self.assertFalse(out["execute_payment"])
        self.assertEqual(pocket.spent, Decimal("170.00"))

    def test_pocket_needs_agent_invoice_and_purpose(self):
        pocket = PercyPocket(cap=Decimal("200.00"))
        for kwargs in [
            {"agent_id": "", "invoice_id": "INV-1", "amount": "10.00", "purpose": "x"},
            {"agent_id": "a", "invoice_id": "", "amount": "10.00", "purpose": "x"},
            {"agent_id": "a", "invoice_id": "INV-1", "amount": "10.00", "purpose": ""},
        ]:
            with self.assertRaises(ValueError):
                pocket.pocket(**kwargs)

    def test_agent_cannot_raise_cap(self):
        pocket = PercyPocket(cap=Decimal("200.00"))
        with self.assertRaises(PermissionError):
            pocket.raise_cap(Decimal("999.00"), by="agent")


if __name__ == "__main__":
    unittest.main()
