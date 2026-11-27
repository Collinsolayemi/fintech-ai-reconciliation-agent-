from __future__ import annotations

from datetime import datetime, timezone
from typing import List
import uuid

from app.core.guardrails import evaluate_guardrails
from app.models.schemas import (
    ActionExecutionRequest,
    ActionExecutionResult,
    RecommendedAction,
)
from app.rag.knowledge_base import record_resolution_outcome

EXECUTION_AUDIT_LOG: List[ActionExecutionResult] = []


async def execute_guardrailed_action(
    req: ActionExecutionRequest,
) -> ActionExecutionResult:
    """
    Module 3 Entrypoint: Execute an investigation or dispute action only if
    guardrails pass (auto-executable OR explicitly approved by a human admin).
    Records an immutable audit log entry and updates RAG memory.
    """
    guardrail = evaluate_guardrails(
        amount=req.amount,
        confidence=req.confidence,
        action=req.action,
    )

    if guardrail.requires_human_approval and not req.approved_by:
        raise PermissionError(
            "Guardrail blocked execution: human approval ('approved_by') is required. "
            f"Reasons: {'; '.join(guardrail.reasons)}"
        )

    exec_id = f"exec-{uuid.uuid4().hex[:10]}"
    idempotency_key = str(uuid.uuid4())
    journal_id = (
        f"JRN-{uuid.uuid4().hex[:8].upper()}"
        if req.action in {RecommendedAction.POST_FEE_ADJUSTMENT, RecommendedAction.REVERSE_DUPLICATE}
        else None
    )

    learned = False
    if req.discrepancy_type and req.resolution_notes:
        record_resolution_outcome(
            pattern=req.discrepancy_type.value,
            error_signature=f"Verified case {req.reference}",
            resolution=req.resolution_notes,
            recommended_action=req.action.value,
        )
        learned = True

    result = ActionExecutionResult(
        execution_id=exec_id,
        reference=req.reference,
        action=req.action,
        status="EXECUTED",
        idempotency_key=idempotency_key,
        approved_by=req.approved_by or "AUTO_GUARDRAIL_POLICY",
        ledger_journal_id=journal_id,
        message=(
            f"Executed {req.action.value} for {req.reference} "
            f"(idempotency_key={idempotency_key})."
        ),
        learned_in_rag=learned,
        executed_at=datetime.now(timezone.utc).isoformat(),
    )
    EXECUTION_AUDIT_LOG.insert(0, result)
    return result


def get_execution_history() -> List[ActionExecutionResult]:
    """Return all recorded action executions in reverse chronological order."""
    return list(EXECUTION_AUDIT_LOG)
