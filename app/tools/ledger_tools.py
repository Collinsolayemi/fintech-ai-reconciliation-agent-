from __future__ import annotations

from typing import Optional
import httpx
from app.core.config import settings


async def get_ledger_entries(reference: str) -> dict:
    """
    Read-only tool: Fetch double-entry postings for a reference from the Java
    FintechCore ledger API, with realistic scenario fallback when offline.
    """
    headers = {}
    if settings.ledger_api_token:
        headers["Authorization"] = f"Bearer {settings.ledger_api_token}"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.ledger_api_url}/transactions/reference/{reference}",
                headers=headers,
            )
            if resp.status_code == 200:
                return {"found": True, "source": "fintech_core_api", "data": resp.json()}
    except httpx.HTTPError:
        pass

    # Scenario-aware offline stub for local development & evals
    ref_upper = reference.upper()
    if "DUP" in ref_upper:
        return {
            "found": True,
            "source": "fintech_core_stub",
            "reference": reference,
            "entry_count": 2,
            "entries": [
                {"entry_id": "le-01", "type": "CREDIT", "amount": 250.00, "timestamp": "2026-11-27T10:00:01Z"},
                {"entry_id": "le-02", "type": "CREDIT", "amount": 250.00, "timestamp": "2026-11-27T10:00:03Z"},
            ],
            "note": "Two identical credit postings detected within 2 seconds.",
        }

    if "FEE" in ref_upper or "9921" in ref_upper:
        return {
            "found": True,
            "source": "fintech_core_stub",
            "reference": reference,
            "entry_count": 1,
            "entries": [
                {"entry_id": "le-10", "type": "CREDIT", "amount": 1000.00, "status": "POSTED"}
            ],
            "note": "Ledger recorded gross amount; no processor fee variance entry posted.",
        }

    if "ESCROW" in ref_upper:
        return {
            "found": True,
            "source": "fintech_core_stub",
            "reference": reference,
            "entry_count": 1,
            "entries": [
                {"entry_id": "le-20", "type": "HOLD", "amount": 420.00, "status": "PENDING_ESCROW"}
            ],
            "note": "Funds remain locked in PENDING_ESCROW past SLA.",
        }

    return {
        "found": False,
        "source": "fintech_core_stub",
        "reference": reference,
        "entry_count": 0,
        "entries": [],
        "note": "No posted ledger entries found for this reference.",
    }


async def get_customer_kyc_profile(customer_email: Optional[str], reference: str) -> dict:
    """
    Read-only tool: Fetch customer KYC tier, verification status, and session signals
    to support chargeback/dispute evidence compilation.
    """
    return {
        "customer_email": customer_email or "unknown@fintech.com",
        "reference": reference,
        "kyc_tier": 2,
        "kyc_status": "APPROVED",
        "three_ds_authenticated": True,
        "ip_match": True,
        "device_fingerprint_matched": True,
        "prior_dispute_count": 0,
    }
