import asyncio
import unittest

from app.agents.reconciliation_agent import investigate_discrepancy
from app.models.schemas import DiscrepancyEvent, DiscrepancyType, RecommendedAction


class TestReconciliationModule(unittest.TestCase):
    def test_low_value_missing_webhook_is_auto_executable(self):
        event = DiscrepancyEvent(
            reference="TXN-2026-9941A",
            provider="STRIPE",
            discrepancy_type=DiscrepancyType.MISSING_LEDGER_ENTRY,
            expected_amount=75.00,
            actual_amount=0.00,
        )
        result = asyncio.run(investigate_discrepancy(event))
        self.assertEqual(result.recommended_action, RecommendedAction.REPLAY_WEBHOOK)
        self.assertTrue(result.guardrail.auto_executable)
        self.assertFalse(result.guardrail.requires_human_approval)
        self.assertEqual(len(result.audit_trail), 3)

    def test_high_value_missing_webhook_requires_human_approval(self):
        event = DiscrepancyEvent(
            reference="TXN-HIGH-5000",
            provider="STRIPE",
            discrepancy_type=DiscrepancyType.MISSING_LEDGER_ENTRY,
            expected_amount=5000.00,
            actual_amount=0.00,
        )
        result = asyncio.run(investigate_discrepancy(event))
        self.assertEqual(result.recommended_action, RecommendedAction.REPLAY_WEBHOOK)
        self.assertTrue(result.guardrail.requires_human_approval)
        self.assertFalse(result.guardrail.auto_executable)

    def test_processor_fee_variance_proposes_fee_adjustment(self):
        event = DiscrepancyEvent(
            reference="TXN-2026-9921C",
            provider="PAYSTACK",
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
            expected_amount=1000.00,
            actual_amount=970.70,
        )
        result = asyncio.run(investigate_discrepancy(event))
        self.assertEqual(result.recommended_action, RecommendedAction.POST_FEE_ADJUSTMENT)
        self.assertTrue(result.guardrail.requires_human_approval)

    def test_duplicate_settlement_proposes_reversal_with_hitl(self):
        event = DiscrepancyEvent(
            reference="TXN-DUP-001",
            provider="STRIPE",
            discrepancy_type=DiscrepancyType.DUPLICATE_SETTLEMENT,
            expected_amount=250.00,
            actual_amount=500.00,
        )
        result = asyncio.run(investigate_discrepancy(event))
        self.assertEqual(result.recommended_action, RecommendedAction.REVERSE_DUPLICATE)
        self.assertTrue(result.guardrail.requires_human_approval)

    def test_stuck_escrow_escalates_to_ops(self):
        event = DiscrepancyEvent(
            reference="TXN-ESCROW-009",
            provider="FLUTTERWAVE",
            discrepancy_type=DiscrepancyType.STUCK_ESCROW,
            expected_amount=420.00,
            actual_amount=0.00,
        )
        result = asyncio.run(investigate_discrepancy(event))
        self.assertEqual(result.recommended_action, RecommendedAction.ESCALATE_TO_OPS)
        self.assertTrue(result.guardrail.requires_human_approval)


if __name__ == "__main__":
    unittest.main()
