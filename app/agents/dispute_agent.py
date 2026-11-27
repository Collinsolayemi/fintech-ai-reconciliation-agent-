from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.core.guardrails import evaluate_guardrails
from app.models.schemas import (
    AuditStep,
    DisputeDraftDiagnosis,
    DisputeDraftResult,
    DisputeEvent,
    RecommendedAction,
)
from app.rag.knowledge_base import retrieve_dispute_playbook
from app.tools.gateway_tools import get_gateway_settlement
from app.tools.ledger_tools import get_customer_kyc_profile, get_ledger_entries

DISPUTE_SYSTEM_PROMPT = """You are an autonomous FinTech Chargeback & Dispute Resolution Specialist.
Your job is to evaluate incoming payment disputes, correlate ledger/gateway/KYC evidence, decide whether to CONTEST or ACCEPT, and draft a factual rebuttal packet.

Rules:
1. Only recommend CONTEST if supporting evidence contradicts the cardholder claim.
2. Recommend ACCEPT if duplicate postings or genuine processing errors are confirmed.
3. Never fabricate transaction IDs, timestamps, or KYC attributes.
4. Return a valid JSON object matching DisputeDraftDiagnosis."""


def _draft_with_llm(
    event: DisputeEvent,
    evidence: Dict[str, Any],
    playbook: Dict[str, Any],
) -> DisputeDraftDiagnosis:
    """Invoke Gemini with structured JSON output grounded in dispute evidence."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = (
        f"Dispute Event:\n{event.model_dump_json(indent=2)}\n\n"
        f"Evidence Collected:\n{json.dumps(evidence, indent=2)}\n\n"
        f"Card-Network Playbook:\n{json.dumps(playbook, indent=2)}\n\n"
        "Decide recommended_stance (CONTEST or ACCEPT), assign confidence (0.0 to 1.0), "
        "list supporting_artifacts, and draft a concise, factual rebuttal_letter."
    )

    response = client.models.generate_content(
        model=settings.llm_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=DISPUTE_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=DisputeDraftDiagnosis,
            temperature=0.1,
        ),
    )
    return DisputeDraftDiagnosis.model_validate_json(response.text)


def _draft_deterministically(
    event: DisputeEvent,
    evidence: Dict[str, Any],
    playbook: Dict[str, Any],
) -> DisputeDraftDiagnosis:
    """Playbook-driven fallback drafter when no LLM API key is configured."""
    ledger = evidence["ledger"]
    gateway = evidence["gateway"]
    kyc = evidence["kyc"]

    entry_count = int(ledger.get("entry_count", 0) or 0)
    is_duplicate = (
        event.reason_code.lower() == "duplicate_processing" or entry_count > 1
    )
    strong_kyc = (
        kyc.get("kyc_status") == "APPROVED"
        and kyc.get("three_ds_authenticated") is True
        and kyc.get("ip_match") is True
    )

    if is_duplicate:
        stance = "ACCEPT"
        confidence = 0.93
        evidence_summary = (
            f"Confirmed {entry_count} ledger postings for {event.transaction_reference}; "
            "dispute is valid and duplicate charge should be refunded."
        )
        rebuttal = (
            f"Internal Dispute Review — {event.dispute_id}\n"
            f"Decision: ACCEPT & REFUND\n"
            f"Transaction: {event.transaction_reference} ({event.currency} {event.amount:,.2f})\n"
            "Finding: Duplicate posting detected in core ledger. Recommend immediate reversal."
        )
    elif strong_kyc:
        stance = "CONTEST"
        confidence = 0.91
        evidence_summary = (
            f"Customer {kyc.get('customer_email')} passed Tier {kyc.get('kyc_tier')} KYC, "
            "3-D Secure authentication, and IP/device fingerprint verification."
        )
        rebuttal = (
            f"Chargeback Rebuttal Packet — {event.dispute_id}\n"
            f"Transaction Reference: {event.transaction_reference}\n"
            f"Reason Code: {event.reason_code} | Amount: {event.currency} {event.amount:,.2f}\n\n"
            "Compelling Evidence:\n"
            f"1. Gateway ({event.provider}) confirmed status '{gateway.get('gateway_status')}'.\n"
            f"2. Cardholder completed 3-D Secure authentication (three_ds_authenticated=True).\n"
            f"3. Customer account is KYC Tier {kyc.get('kyc_tier')} ({kyc.get('kyc_status')}) "
            "with matching IP and device fingerprint.\n"
            f"4. Prior dispute history: {kyc.get('prior_dispute_count', 0)}."
        )
    else:
        stance = "CONTEST"
        confidence = 0.68
        evidence_summary = "Partial settlement proof available; manual evidence review advised."
        rebuttal = (
            f"Preliminary Dispute Draft — {event.dispute_id}\n"
            f"Transaction: {event.transaction_reference} ({event.currency} {event.amount:,.2f})\n"
            "Note: Additional customer delivery or session logs recommended before submission."
        )

    artifacts = [
        f"Ledger Posting Record ({event.transaction_reference})",
        f"{event.provider} Settlement Receipt ({gateway.get('gateway_status')})",
        *playbook.get("required_evidence", []),
    ]

    return DisputeDraftDiagnosis(
        recommended_stance=stance,
        confidence=confidence,
        evidence_summary=evidence_summary,
        rebuttal_letter=rebuttal,
        supporting_artifacts=artifacts,
    )


async def _gather_dispute_evidence(
    event: DisputeEvent,
) -> Tuple[Dict[str, Any], List[AuditStep]]:
    """Collect ledger, gateway, and KYC evidence with full audit logging."""
    audit_trail: List[AuditStep] = []

    ledger_data = await get_ledger_entries(event.transaction_reference)
    audit_trail.append(
        AuditStep(
            tool_name="get_ledger_entries",
            arguments={"reference": event.transaction_reference},
            observation_summary=f"found={ledger_data.get('found')}, entries={ledger_data.get('entry_count', 0)}",
        )
    )

    gateway_data = await get_gateway_settlement(event.transaction_reference, event.provider)
    audit_trail.append(
        AuditStep(
            tool_name="get_gateway_settlement",
            arguments={"reference": event.transaction_reference, "provider": event.provider},
            observation_summary=f"status={gateway_data.get('gateway_status')}, net={gateway_data.get('net_settled')}",
        )
    )

    kyc_data = await get_customer_kyc_profile(
        event.customer_email, event.transaction_reference
    )
    audit_trail.append(
        AuditStep(
            tool_name="get_customer_kyc_profile",
            arguments={"customer_email": event.customer_email, "reference": event.transaction_reference},
            observation_summary=(
                f"kyc_tier={kyc_data.get('kyc_tier')}, 3ds={kyc_data.get('three_ds_authenticated')}, "
                f"ip_match={kyc_data.get('ip_match')}"
            ),
        )
    )

    return {"ledger": ledger_data, "gateway": gateway_data, "kyc": kyc_data}, audit_trail


async def draft_dispute_response(event: DisputeEvent) -> DisputeDraftResult:
    """
    Module 2 Entrypoint: Gather transaction, gateway, and KYC evidence,
    apply card-network playbooks, and draft a chargeback rebuttal packet
    with mandatory HITL guardrail enforcement.
    """
    evidence, audit_trail = await _gather_dispute_evidence(event)
    playbook = retrieve_dispute_playbook(event.reason_code)

    engine_mode = "deterministic_fallback"
    if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
        try:
            draft = _draft_with_llm(event, evidence, playbook)
            engine_mode = "gemini_llm"
        except Exception:
            draft = _draft_deterministically(event, evidence, playbook)
    else:
        draft = _draft_deterministically(event, evidence, playbook)

    guardrail = evaluate_guardrails(
        amount=event.amount,
        confidence=draft.confidence,
        action=RecommendedAction.ESCALATE_TO_OPS,
    )

    return DisputeDraftResult(
        dispute_id=event.dispute_id,
        transaction_reference=event.transaction_reference,
        engine_mode=engine_mode,
        recommended_stance=draft.recommended_stance,
        confidence=draft.confidence,
        evidence_summary=draft.evidence_summary,
        rebuttal_letter=draft.rebuttal_letter,
        supporting_artifacts=draft.supporting_artifacts,
        guardrail=guardrail,
        audit_trail=audit_trail,
    )
