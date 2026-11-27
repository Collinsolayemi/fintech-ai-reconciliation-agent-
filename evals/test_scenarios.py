import asyncio
import unittest

from app.agents.dispute_agent import draft_dispute_response
from app.agents.reconciliation_agent import investigate_discrepancy
from app.models.schemas import (
    ActionExecutionRequest,
    DiscrepancyEvent,
    DiscrepancyType,
    DisputeEvent,
    RecommendedAction,
)
from app.rag.knowledge_base import list_all_cases
from app.services.action_executor import execute_guardrailed_action, get_execution_history


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


class TestDisputeResolutionModule(unittest.TestCase):
    def test_fraudulent_dispute_with_kyc_and_3ds_recommends_contest(self):
        event = DisputeEvent(
            dispute_id="dp_1Qx9941A",
            transaction_reference="TXN-2026-9938B",
            provider="STRIPE",
            reason_code="fraudulent",
            amount=2450.00,
            currency="USD",
            customer_email="john.doe@fintech.com",
        )
        result = asyncio.run(draft_dispute_response(event))
        self.assertEqual(result.recommended_stance, "CONTEST")
        self.assertTrue(result.guardrail.requires_human_approval)
        self.assertEqual(len(result.audit_trail), 3)
        self.assertIn("3-D Secure", result.rebuttal_letter)

    def test_duplicate_processing_dispute_recommends_accept(self):
        event = DisputeEvent(
            dispute_id="dp_DUP001",
            transaction_reference="TXN-DUP-001",
            provider="STRIPE",
            reason_code="duplicate_processing",
            amount=250.00,
            currency="USD",
            customer_email="john.doe@fintech.com",
        )
        result = asyncio.run(draft_dispute_response(event))
        self.assertEqual(result.recommended_stance, "ACCEPT")
        self.assertTrue(result.guardrail.requires_human_approval)
        self.assertIn("ACCEPT & REFUND", result.rebuttal_letter)


class TestActionExecutorAndRagModule(unittest.TestCase):
    def test_high_value_action_without_approval_is_blocked(self):
        req = ActionExecutionRequest(
            reference="TXN-BLOCK-01",
            action=RecommendedAction.REPLAY_WEBHOOK,
            amount=5000.00,
            confidence=0.96,
        )
        with self.assertRaises(PermissionError):
            asyncio.run(execute_guardrailed_action(req))

    def test_low_value_auto_action_executes_without_human_approval(self):
        req = ActionExecutionRequest(
            reference="TXN-AUTO-01",
            action=RecommendedAction.REPLAY_WEBHOOK,
            amount=50.00,
            confidence=0.95,
        )
        result = asyncio.run(execute_guardrailed_action(req))
        self.assertEqual(result.status, "EXECUTED")
        self.assertEqual(result.approved_by, "AUTO_GUARDRAIL_POLICY")
        self.assertTrue(len(get_execution_history()) >= 1)

    def test_hitl_approved_fee_adjustment_executes_and_learns_in_rag(self):
        initial_count = len(list_all_cases())
        req = ActionExecutionRequest(
            reference="TXN-FEE-99",
            action=RecommendedAction.POST_FEE_ADJUSTMENT,
            amount=29.30,
            confidence=0.92,
            approved_by="admin@fintech.com",
            discrepancy_type=DiscrepancyType.AMOUNT_MISMATCH,
            resolution_notes="Confirmed 2.9% + $0.30 Paystack fee deduction.",
        )
        result = asyncio.run(execute_guardrailed_action(req))
        self.assertEqual(result.status, "EXECUTED")
        self.assertIsNotNone(result.ledger_journal_id)
        self.assertTrue(result.learned_in_rag)
        self.assertEqual(len(list_all_cases()), initial_count + 1)


if __name__ == "__main__":
    unittest.main()
