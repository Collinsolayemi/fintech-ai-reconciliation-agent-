from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DiscrepancyType(str, Enum):
    MISSING_LEDGER_ENTRY = "MISSING_LEDGER_ENTRY"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE_SETTLEMENT = "DUPLICATE_SETTLEMENT"
    STUCK_ESCROW = "STUCK_ESCROW"
    UNKNOWN = "UNKNOWN"


class RecommendedAction(str, Enum):
    REPLAY_WEBHOOK = "REPLAY_WEBHOOK"
    POST_FEE_ADJUSTMENT = "POST_FEE_ADJUSTMENT"
    REVERSE_DUPLICATE = "REVERSE_DUPLICATE"
    ESCALATE_TO_OPS = "ESCALATE_TO_OPS"
    NO_ACTION = "NO_ACTION"


class DiscrepancyEvent(BaseModel):
    reference: str = Field(..., description="Transaction or payout reference")
    provider: str = Field(default="STRIPE", description="Payment gateway name")
    discrepancy_type: DiscrepancyType
    expected_amount: float
    actual_amount: float
    currency: str = "USD"
    raw_details: Optional[str] = None


class DisputeEvent(BaseModel):
    dispute_id: str
    transaction_reference: str
    provider: str = "STRIPE"
    reason_code: str = Field(..., description="e.g. fraudulent, product_not_received")
    amount: float
    currency: str = "USD"
    customer_email: Optional[str] = None
    notes: Optional[str] = None


class AuditStep(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    observation_summary: str


class GuardrailDecision(BaseModel):
    requires_human_approval: bool
    auto_executable: bool
    reasons: List[str]


class AgentDiagnosis(BaseModel):
    """Structured output schema returned by the LLM after tool-based investigation."""

    root_cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_action: RecommendedAction
    reasoning_summary: str


class InvestigationResult(BaseModel):
    reference: str
    engine_mode: str = Field(
        default="deterministic_fallback",
        description="Whether diagnosis came from 'gemini_llm' or 'deterministic_fallback'",
    )
    root_cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_action: RecommendedAction
    reasoning_summary: str
    guardrail: GuardrailDecision
    audit_trail: List[AuditStep] = []


class BatchInvestigationRequest(BaseModel):
    discrepancies: List[DiscrepancyEvent]


class BatchInvestigationResult(BaseModel):
    total: int
    auto_executable_count: int
    requires_approval_count: int
    results: List[InvestigationResult]


class DisputeDraftDiagnosis(BaseModel):
    """Structured output schema returned by the LLM for dispute rebuttal drafting."""

    recommended_stance: str  # CONTEST or ACCEPT
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_summary: str
    rebuttal_letter: str
    supporting_artifacts: List[str]


class DisputeDraftResult(BaseModel):
    dispute_id: str
    transaction_reference: str
    engine_mode: str = "deterministic_fallback"
    recommended_stance: str  # CONTEST or ACCEPT
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_summary: str
    rebuttal_letter: str
    supporting_artifacts: List[str]
    guardrail: GuardrailDecision
    audit_trail: List[AuditStep] = []


class ActionExecutionRequest(BaseModel):
    reference: str
    action: RecommendedAction
    amount: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    currency: str = "USD"
    approved_by: Optional[str] = Field(
        default=None,
        description="Admin email/ID required when guardrail requires human approval",
    )
    resolution_notes: Optional[str] = None
    discrepancy_type: Optional[DiscrepancyType] = None


class ActionExecutionResult(BaseModel):
    execution_id: str
    reference: str
    action: RecommendedAction
    status: str  # EXECUTED, REJECTED_BY_GUARDRAIL
    idempotency_key: str
    approved_by: Optional[str] = None
    ledger_journal_id: Optional[str] = None
    message: str
    learned_in_rag: bool = False
    executed_at: str
