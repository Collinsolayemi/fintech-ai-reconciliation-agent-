from fastapi import FastAPI
from app.agents.dispute_agent import draft_dispute_response
from app.agents.reconciliation_agent import investigate_discrepancy
from app.models.schemas import (
    DiscrepancyEvent,
    DisputeDraftResult,
    DisputeEvent,
    InvestigationResult,
)

app = FastAPI(
    title="Fintech AI Reconciliation & Dispute Agent",
    version="0.1.0",
    description="Autonomous investigation and dispute-drafting service for double-entry payment ledgers.",
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "fintech-ai-reconciliation-agent"}


@app.post("/agent/investigate", response_model=InvestigationResult)
async def run_investigation(event: DiscrepancyEvent):
    return await investigate_discrepancy(event)


@app.post("/agent/disputes/draft", response_model=DisputeDraftResult)
async def run_dispute_draft(event: DisputeEvent):
    return await draft_dispute_response(event)
