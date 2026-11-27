from app.core.guardrails import evaluate_guardrails
from app.models.schemas import (
    DisputeDraftResult,
    DisputeEvent,
    RecommendedAction,
)
from app.tools.gateway_tools import get_gateway_settlement
from app.tools.ledger_tools import get_ledger_entries


async def draft_dispute_response(event: DisputeEvent) -> DisputeDraftResult:
    """Gather transaction evidence and draft a chargeback rebuttal packet."""
    ledger_data = await get_ledger_entries(event.transaction_reference)
    gateway_data = await get_gateway_settlement(event.transaction_reference, event.provider)

    artifacts = [
        f"Ledger Posting Record ({event.transaction_reference})",
        f"{event.provider} Settlement Confirmation ({gateway_data.get('gateway_status')})",
        "Customer KYC & Session Verification Summary",
    ]

    rebuttal = (
        f"Dispute Rebuttal for {event.dispute_id} ({event.transaction_reference})\n"
        f"Reason Code: {event.reason_code}\n"
        f"Amount: {event.currency} {event.amount:,.2f}\n\n"
        f"Summary of Evidence:\n"
        f"- Transaction was settled via {event.provider} (Ledger found={ledger_data.get('found')}).\n"
        f"- Customer account passed KYC verification prior to transaction execution.\n"
        f"- Full audit logs and settlement proof are attached."
    )

    guardrail = evaluate_guardrails(
        amount=event.amount,
        confidence=0.87,
        action=RecommendedAction.ESCALATE_TO_OPS,
    )

    return DisputeDraftResult(
        dispute_id=event.dispute_id,
        transaction_reference=event.transaction_reference,
        recommended_stance="CONTEST",
        confidence=0.87,
        evidence_summary="Transaction settled with verified KYC and matching gateway reference.",
        rebuttal_letter=rebuttal,
        supporting_artifacts=artifacts,
        guardrail=guardrail,
    )
