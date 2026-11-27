from app.core.guardrails import evaluate_guardrails
from app.models.schemas import (
    AuditStep,
    DiscrepancyEvent,
    DiscrepancyType,
    InvestigationResult,
    RecommendedAction,
)
from app.rag.knowledge_base import retrieve_similar_cases
from app.tools.gateway_tools import get_gateway_settlement, get_webhook_logs
from app.tools.ledger_tools import get_ledger_entries


async def investigate_discrepancy(event: DiscrepancyEvent) -> InvestigationResult:
    """
    Investigate a payment reconciliation discrepancy using read-only tools,
    RAG memory, and deterministic financial guardrails.
    """
    audit_trail: list[AuditStep] = []

    # 1. Gather evidence via read-only tools
    ledger_data = await get_ledger_entries(event.reference)
    audit_trail.append(
        AuditStep(
            tool_name="get_ledger_entries",
            arguments={"reference": event.reference},
            observation_summary=f"found={ledger_data.get('found')}",
        )
    )

    gateway_data = await get_gateway_settlement(event.reference, event.provider)
    audit_trail.append(
        AuditStep(
            tool_name="get_gateway_settlement",
            arguments={"reference": event.reference, "provider": event.provider},
            observation_summary=f"status={gateway_data.get('gateway_status')}, net={gateway_data.get('net_settled')}",
        )
    )

    webhook_data = await get_webhook_logs(event.reference)
    audit_trail.append(
        AuditStep(
            tool_name="get_webhook_logs",
            arguments={"reference": event.reference},
            observation_summary=f"attempts={len(webhook_data.get('delivery_attempts', []))}",
        )
    )

    # 2. Retrieve historical resolution patterns (RAG)
    similar_cases = retrieve_similar_cases(event.discrepancy_type.value)

    # 3. Synthesize diagnosis (hook in Gemini / LLM structured output here)
    if event.discrepancy_type == DiscrepancyType.MISSING_LEDGER_ENTRY:
        root_cause = "Gateway settled transaction, but webhook failed with 504 timeout."
        action = RecommendedAction.REPLAY_WEBHOOK
        confidence = 0.94
    elif event.discrepancy_type == DiscrepancyType.AMOUNT_MISMATCH:
        root_cause = "Processor fee deducted prior to settlement."
        action = RecommendedAction.POST_FEE_ADJUSTMENT
        confidence = 0.91
    elif event.discrepancy_type == DiscrepancyType.DUPLICATE_SETTLEMENT:
        root_cause = "Duplicate gateway settlement detected for the same reference."
        action = RecommendedAction.REVERSE_DUPLICATE
        confidence = 0.88
    else:
        root_cause = "Unclassified discrepancy requiring manual operations review."
        action = RecommendedAction.ESCALATE_TO_OPS
        confidence = 0.55

    variance = abs(event.expected_amount - event.actual_amount)
    guardrail = evaluate_guardrails(amount=variance, confidence=confidence, action=action)

    rag_note = f" Matched {len(similar_cases)} historical case(s)." if similar_cases else ""
    return InvestigationResult(
        reference=event.reference,
        root_cause=root_cause,
        confidence=confidence,
        recommended_action=action,
        reasoning_summary=(
            f"Inspected ledger, {event.provider} settlement, and webhook logs for {event.reference}."
            f"{rag_note}"
        ),
        guardrail=guardrail,
        audit_trail=audit_trail,
    )
