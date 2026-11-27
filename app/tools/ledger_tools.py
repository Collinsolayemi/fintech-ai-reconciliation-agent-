import httpx
from app.core.config import settings


async def get_ledger_entries(reference: str) -> dict:
    """Fetch double-entry postings for a reference from the Java FintechCore ledger."""
    headers = {}
    if settings.ledger_api_token:
        headers["Authorization"] = f"Bearer {settings.ledger_api_token}"

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                f"{settings.ledger_api_url}/transactions/reference/{reference}",
                headers=headers,
            )
            if resp.status_code == 200:
                return {"found": True, "source": "fintech_core_api", "data": resp.json()}
    except httpx.HTTPError:
        pass

    return {
        "found": False,
        "source": "fintech_core_api_offline_stub",
        "reference": reference,
        "entries": [],
        "note": "No posted ledger entries found for this reference.",
    }
