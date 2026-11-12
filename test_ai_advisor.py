import unittest
from decimal import Decimal

from ai_advisor import eligible_candidates, recommend

CANDIDATES = [
    {"invoice_id": "INV-001", "purpose": "supplier invoice", "amount": "60.00"},
    {"invoice_id": "INV-002", "purpose": "supplier invoice", "amount": "70.00"},
    {"invoice_id": "INV-003", "purpose": "equipment invoice", "amount": "250.00"},
]


class TestAdvisor(unittest.TestCase):
    def test_server_filters_over_cap_candidates(self):
        eligible = eligible_candidates(CANDIDATES, Decimal("200"))
        self.assertEqual([c["invoice_id"] for c in eligible], ["INV-001", "INV-002"])

    def test_local_rule_mode_is_labeled_honestly(self):
        chosen, receipt = recommend(CANDIDATES, Decimal("200"))
        self.assertEqual(chosen["invoice_id"], "INV-001")  # smallest eligible
        self.assertEqual(receipt["mode"], "LOCAL_RULE_AGENT")

    def test_model_pick_within_eligible_is_used(self):
        chosen, receipt = recommend(
            CANDIDATES, Decimal("200"), ai_client=lambda eligible: "INV-002"
        )
        self.assertEqual(chosen["invoice_id"], "INV-002")
        self.assertEqual(receipt["mode"], "AI_MODEL")

    def test_model_cannot_invent_or_pick_ineligible(self):
        for bad_pick in ("INV-003", "INV-999"):
            chosen, receipt = recommend(
                CANDIDATES, Decimal("200"),
                ai_client=lambda eligible, bad=bad_pick: bad,
            )
            self.assertEqual(receipt["mode"], "LOCAL_RULE_AGENT")
            self.assertEqual(chosen["invoice_id"], "INV-001")

    def test_model_failure_falls_back_and_labels(self):
        def boom(eligible):
            raise RuntimeError("down")

        chosen, receipt = recommend(CANDIDATES, Decimal("200"), ai_client=boom)
        self.assertEqual(receipt["mode"], "LOCAL_RULE_AGENT")
        self.assertIsNotNone(chosen)

    def test_nothing_eligible_blocks(self):
        chosen, receipt = recommend(CANDIDATES, Decimal("10"))
        self.assertIsNone(chosen)
        self.assertEqual(receipt["mode"], "blocked")


if __name__ == "__main__":
    unittest.main()
