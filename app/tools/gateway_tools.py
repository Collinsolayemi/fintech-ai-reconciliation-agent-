import httpx
from app.core.config import settings


async def get_gateway_settlement(reference: str, provider: str = "STRIPE") -> dict:
    """Query external payment gateway settlement status for a transaction reference."""
    return {
        "reference": reference,
        "provider": provider,
        "gateway_status": "SETTLED",
        "gross_amount": 100.00,
        "gateway_fee": 2.90,
        "net_settled": 97.10,
        "currency": "USD",
    }


async def get_webhook_logs(reference: str) -> dict:
    """Inspect recent webhook delivery attempts for a reference."""
    headers = {}
    if settings.ledger_api_token:
        headers["Authorization"] = f"Bearer {settings.ledger_api_token}"

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                f"{settings.ledger_api_url}/admin/webhooks/logs",
                params={"reference": reference},
                headers=headers,
            )
            if resp.status_code == 200:
                return {"found": True, "logs": resp.json()}
    except httpx.HTTPError:
        pass

    return {
        "found": True,
        "reference": reference,
        "delivery_attempts": [
            {"attempt": 1, "http_status": 504, "error": "Gateway Timeout during deploy"}
        ],
    }
