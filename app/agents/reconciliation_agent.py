from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.core.guardrails import evaluate_guardrails
from app.models.schemas import (
    AgentDiagnosis,
    AuditStep,
    DiscrepancyEvent,
    DiscrepancyType,
    InvestigationResult,
    RecommendedAction,
)
from app.rag.knowledge_base import retrieve_similar_cases
from app.tools.gateway_tools import get_gateway_settlement, get_webhook_logs
from app.tools.ledger_tools import get_ledger_entries

SYSTEM_PROMPT = """You are an autonomous FinTech Payment Reconciliation Investigator.
Your job is to diagnose payment discrepancies between an internal double-entry ledger and external payment gateways.

Rules:
1. NEVER invent transaction amounts or claim a balance was updated.
2. Base your diagnosis strictly on the tool observations and historical RAG cases provided.
3. Choose the safest recommended_action from:
   REPLAY_WEBHOOK, POST_FEE_ADJUSTMENT, REVERSE_DUPLICATE, ESCALATE_TO_OPS, NO_ACTION.
4. Return a valid JSON object matching AgentDiagnosis."""


def _analyze_with_llm(
    event: DiscrepancyEvent,
    evidence: Dict[str, Any],
    similar_cases: List[Dict[str, Any]],
) -> AgentDiagnosis:
    """Invoke Gemini with structured JSON output grounded in tool observations."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = (
        f"Discrepancy Event:\n{event.model_dump_json(indent=2)}\n\n"
        f"Tool Observations:\n{json.dumps(evidence, indent=2)}\n\n"
        f"Similar Historical Cases (RAG):\n{json.dumps(similar_cases, indent=2)}\n\n"
        "Diagnose the root cause, assign a confidence score (0.0 to 1.0), "
        "select recommended_action, and summarize your reasoning."
    )

    response = client.models.generate_content(
        model=settings.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=AgentDiagnosis,
            temperature=0.1,
        ),
    )
    return AgentDiagnosis.model_validate_json(response.text or "{}")


def _analyze_deterministically(
    event: DiscrepancyEvent,
    evidence: Dict[str, Any],
    similar_cases: List[Dict[str, Any]],
) -> AgentDiagnosis:
    """Tool-observation-driven fallback analyzer when no LLM API key is configured."""
    ledger = evidence["ledger"]
    gateway = evidence["gateway"]
    webhooks = evidence["webhooks"]

    attempts = webhooks.get("delivery_attempts", [])
    has_webhook_failure = any(a.get("http_status", 200) >= 500 for a in attempts)
    gateway_fee = float(gateway.get("gateway_fee", 0.0) or 0.0)
    entry_count = int(ledger.get("entry_count", 0) or 0)
    has_stuck_escrow = any(
        e.get("status") == "PENDING_ESCROW" for e in ledger.get("entries", [])
    )

    if not ledger.get("found") and gateway.get("gateway_status") == "SETTLED" and has_webhook_failure:
        root_cause = (
            f"{event.provider} settled {event.currency} {gateway.get('net_settled', event.expected_amount):,.2f}, "
            "but webhook delivery failed with HTTP 504 timeout before ledger posting."
        )
        action = RecommendedAction.REPLAY_WEBHOOK
        confidence = 0.95
    elif gateway_fee > 0 and abs((event.expected_amount - event.actual_amount) - gateway_fee) < 1.0:
        root_cause = (
            f"Processor fee ({event.currency} {gateway_fee:,.2f}) was deducted at source "
            f"by {event.provider} prior to net settlement."
        )
        action = RecommendedAction.POST_FEE_ADJUSTMENT
        confidence = 0.92
    elif entry_count > 1 or event.discrepancy_type == DiscrepancyType.DUPLICATE_SETTLEMENT:
        root_cause = (
            f"Duplicate credit postings ({entry_count} entries) detected for reference {event.reference}."
        )
        action = RecommendedAction.REVERSE_DUPLICATE
        confidence = 0.89
    elif has_stuck_escrow or event.discrepancy_type == DiscrepancyType.STUCK_ESCROW:
        root_cause = "Funds remain locked in PENDING_ESCROW despite completed gateway settlement."
        action = RecommendedAction.ESCALATE_TO_OPS
        confidence = 0.82
    else:
        root_cause = "Unclassified discrepancy between internal ledger and gateway settlement."
        action = RecommendedAction.ESCALATE_TO_OPS
        confidence = 0.55

    rag_note = f" Matched {len(similar_cases)} historical case(s)." if similar_cases else ""
    return AgentDiagnosis(
        root_cause=root_cause,
        confidence=confidence,
        recommended_action=action,
        reasoning_summary=(
            f"Inspected ledger (found={ledger.get('found')}), {event.provider} settlement "
            f"(status={gateway.get('gateway_status')}), and {len(attempts)} webhook log(s).{rag_note}"
        ),
    )


async def _gather_evidence(event: DiscrepancyEvent) -> Tuple[Dict[str, Any], List[AuditStep]]:
    """Run read-only investigation tools and build an immutable audit trail."""
    audit_trail: List[AuditStep] = []

    ledger_data = await get_ledger_entries(event.reference)
    audit_trail.append(
        AuditStep(
            tool_name="get_ledger_entries",
            arguments={"reference": event.reference},
            observation_summary=f"found={ledger_data.get('found')}, entries={ledger_data.get('entry_count', 0)}",
        )
    )

    gateway_data = await get_gateway_settlement(event.reference, event.provider)
    audit_trail.append(
        AuditStep(
            tool_name="get_gateway_settlement",
            arguments={"reference": event.reference, "provider": event.provider},
            observation_summary=(
                f"status={gateway_data.get('gateway_status')}, "
                f"net={gateway_data.get('net_settled')}, fee={gateway_data.get('gateway_fee', 0)}"
            ),
        )
    )

    webhook_data = await get_webhook_logs(event.reference)
    attempts = webhook_data.get("delivery_attempts", [])
    statuses = [a.get("http_status") for a in attempts]
    audit_trail.append(
        AuditStep(
            tool_name="get_webhook_logs",
            arguments={"reference": event.reference},
            observation_summary=f"attempts={len(attempts)}, statuses={statuses}",
        )
    )

    return {"ledger": ledger_data, "gateway": gateway_data, "webhooks": webhook_data}, audit_trail


async def investigate_discrepancy(event: DiscrepancyEvent) -> InvestigationResult:
    """
    Module 1 Entrypoint: Investigate a payment reconciliation discrepancy using
    read-only tools, RAG memory, LLM reasoning (with deterministic fallback),
    and financial guardrails.
    """
    evidence, audit_trail = await _gather_evidence(event)
    similar_cases = retrieve_similar_cases(event.discrepancy_type.value)

    engine_mode = "deterministic_fallback"
    if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
        try:
            diagnosis = _analyze_with_llm(event, evidence, similar_cases)
            engine_mode = "gemini_llm"
        except Exception:
            diagnosis = _analyze_deterministically(event, evidence, similar_cases)
    else:
        diagnosis = _analyze_deterministically(event, evidence, similar_cases)

    variance = abs(event.expected_amount - event.actual_amount)
    guardrail = evaluate_guardrails(
        amount=variance,
        confidence=diagnosis.confidence,
        action=diagnosis.recommended_action,
    )

    return InvestigationResult(
        reference=event.reference,
        engine_mode=engine_mode,
        root_cause=diagnosis.root_cause,
        confidence=diagnosis.confidence,
        recommended_action=diagnosis.recommended_action,
        reasoning_summary=diagnosis.reasoning_summary,
        guardrail=guardrail,
        audit_trail=audit_trail,
    )
