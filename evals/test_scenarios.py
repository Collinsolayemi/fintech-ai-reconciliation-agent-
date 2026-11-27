import asyncio
from app.agents.reconciliation_agent import investigate_discrepancy
from app.models.schemas import DiscrepancyEvent, DiscrepancyType, RecommendedAction


def test_low_value_missing_webhook_auto_executable():
    event = DiscrepancyEvent(
        reference="TXN-TEST-001",
        provider="STRIPE",
        discrepancy_type=DiscrepancyType.MISSING_LEDGER_ENTRY,
        expected_amount=50.00,
        actual_amount=0.00,
    )
    result = asyncio.run(investigate_discrepancy(event))
    assert result.recommended_action == RecommendedAction.REPLAY_WEBHOOK
    assert result.guardrail.auto_executable is True
    assert result.guardrail.requires_human_approval is False


def test_high_value_discrepancy_requires_human_approval():
    event = DiscrepancyEvent(
        reference="TXN-TEST-002",
        provider="STRIPE",
        discrepancy_type=DiscrepancyType.MISSING_LEDGER_ENTRY,
        expected_amount=5000.00,
        actual_amount=0.00,
    )
    result = asyncio.run(investigate_discrepancy(event))
    assert result.guardrail.requires_human_approval is True
    assert result.guardrail.auto_executable is False
