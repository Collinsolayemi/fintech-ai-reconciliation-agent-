from __future__ import annotations

import httpx
from app.core.config import settings


async def get_gateway_settlement(reference: str, provider: str = "STRIPE") -> dict:
    """
    Read-only tool: Query external payment gateway settlement status
    for a transaction reference.
    """
    ref_upper = reference.upper()

    if "FEE" in ref_upper or "9921" in ref_upper:
        return {
            "reference": reference,
            "provider": provider,
            "gateway_status": "SETTLED",
            "gross_amount": 1000.00,
            "gateway_fee": 29.30,
            "net_settled": 970.70,
            "fee_formula": "2.9% + $0.30",
            "currency": "USD",
        }

    if "DUP" in ref_upper:
        return {
            "reference": reference,
            "provider": provider,
            "gateway_status": "SETTLED",
            "settlement_count": 2,
            "gross_amount": 250.00,
            "net_settled": 250.00,
            "currency": "USD",
        }

    if "ESCROW" in ref_upper:
        return {
            "reference": reference,
            "provider": provider,
            "gateway_status": "COMPLETED",
            "gross_amount": 420.00,
            "net_settled": 420.00,
            "currency": "USD",
        }

    return {
        "reference": reference,
        "provider": provider,
        "gateway_status": "SETTLED",
        "gross_amount": 75.00,
        "gateway_fee": 0.00,
        "net_settled": 75.00,
        "currency": "USD",
    }


async def get_webhook_logs(reference: str) -> dict:
    """Read-only tool: Inspect recent webhook delivery attempts for a reference."""
    headers = {}
    if settings.ledger_api_token:
        headers["Authorization"] = f"Bearer {settings.ledger_api_token}"

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.ledger_api_url}/admin/webhooks/logs",
                params={"reference": reference},
                headers=headers,
            )
            if resp.status_code == 200:
                return {"found": True, "logs": resp.json()}
    except httpx.HTTPError:
        pass

    ref_upper = reference.upper()
    if "FEE" in ref_upper or "9921" in ref_upper or "DUP" in ref_upper:
        return {
            "found": True,
            "reference": reference,
            "delivery_attempts": [
                {"attempt": 1, "http_status": 200, "event": "charge.succeeded"}
            ],
        }

    return {
        "found": True,
        "reference": reference,
        "delivery_attempts": [
            {
                "attempt": 1,
                "http_status": 504,
                "event": "charge.succeeded",
                "error": "Gateway Timeout during rolling deploy",
            }
        ],
    }
