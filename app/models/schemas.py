from enum import Enum
from typing import Any, Optional
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
    arguments: dict[str, Any]
    observation_summary: str


class GuardrailDecision(BaseModel):
    requires_human_approval: bool
    auto_executable: bool
    reasons: list[str]


class InvestigationResult(BaseModel):
    reference: str
    root_cause: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    recommended_action: RecommendedAction
    reasoning_summary: str
    guardrail: GuardrailDecision
    audit_trail: list[AuditStep] = []


class DisputeDraftResult(BaseModel):
    dispute_id: str
    transaction_reference: str
    recommended_stance: str  # CONTEST or ACCEPT
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_summary: str
    rebuttal_letter: str
    supporting_artifacts: list[str]
    guardrail: GuardrailDecision
