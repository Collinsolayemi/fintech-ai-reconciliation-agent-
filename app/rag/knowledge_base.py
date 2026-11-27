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


DISPUTE_PLAYBOOKS = {
    "fraudulent": {
        "required_evidence": [
            "3-D Secure (3DS) authentication log",
            "KYC Tier 2+ identity verification record",
            "Matching IP address and device fingerprint history",
        ],
        "guidance": "Contest when 3DS passed and KYC/device signals match cardholder.",
    },
    "product_not_received": {
        "required_evidence": [
            "API access / service delivery timestamps",
            "Signed receipt or webhook fulfillment confirmation",
        ],
        "guidance": "Contest with timestamped digital fulfillment and usage logs.",
    },
    "duplicate_processing": {
        "required_evidence": [
            "Ledger posting count for transaction reference",
            "Idempotency key audit log",
        ],
        "guidance": "Accept dispute and reverse duplicate if 2+ identical postings exist.",
    },
}


def retrieve_similar_cases(discrepancy_type: str) -> list[dict]:
    """Retrieve historical resolution patterns (replace with pgvector similarity search)."""
    return [case for case in HISTORICAL_CASES if case["pattern"] == discrepancy_type]


def retrieve_dispute_playbook(reason_code: str) -> dict:
    """Retrieve card-network evidence requirements for a dispute reason code."""
    return DISPUTE_PLAYBOOKS.get(
        reason_code.lower(),
        {
            "required_evidence": ["Ledger posting record", "Gateway settlement receipt"],
            "guidance": "Review evidence manually before contesting.",
        },
    )
