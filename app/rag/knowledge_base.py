HISTORICAL_CASES = [
    {
        "pattern": "MISSING_LEDGER_ENTRY",
        "error_signature": "504 Gateway Timeout on webhook delivery",
        "resolution": "Webhook dropped during transient outage; safe to replay idempotent webhook.",
        "recommended_action": "REPLAY_WEBHOOK",
    },
    {
        "pattern": "AMOUNT_MISMATCH",
        "error_signature": "Net settlement lower than gross by ~2.9% + $0.30",
        "resolution": "Processor fee deducted at source before settlement; post fee variance adjustment.",
        "recommended_action": "POST_FEE_ADJUSTMENT",
    },
    {
        "pattern": "DUPLICATE_SETTLEMENT",
        "error_signature": "Two identical credits within 5 seconds without idempotency key",
        "resolution": "Duplicate gateway settlement detected; reverse duplicate entry after ops review.",
        "recommended_action": "REVERSE_DUPLICATE",
    },
]


def retrieve_similar_cases(discrepancy_type: str) -> list[dict]:
    """Retrieve historical resolution patterns (replace with pgvector similarity search)."""
    return [case for case in HISTORICAL_CASES if case["pattern"] == discrepancy_type]
