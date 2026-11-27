from app.core.config import settings
from app.models.schemas import GuardrailDecision, RecommendedAction


SAFE_AUTO_ACTIONS = {RecommendedAction.REPLAY_WEBHOOK, RecommendedAction.NO_ACTION}


def evaluate_guardrails(
    amount: float,
    confidence: float,
    action: RecommendedAction,
) -> GuardrailDecision:
    """Enforce deterministic safety rules before any agent action can execute."""
    reasons: list[str] = []

    if confidence < settings.min_confidence_threshold:
        reasons.append(
            f"Confidence {confidence:.2f} is below threshold {settings.min_confidence_threshold:.2f}."
        )

    if abs(amount) > settings.auto_resolve_max_amount:
        reasons.append(
            f"Amount ${abs(amount):,.2f} exceeds auto-resolve limit ${settings.auto_resolve_max_amount:,.2f}."
        )

    if action not in SAFE_AUTO_ACTIONS:
        reasons.append(f"Action '{action.value}' always requires human approval.")

    requires_human_approval = len(reasons) > 0
    return GuardrailDecision(
        requires_human_approval=requires_human_approval,
        auto_executable=not requires_human_approval,
        reasons=reasons if reasons else ["Passed all automated safety thresholds."],
    )
