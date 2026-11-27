from __future__ import annotations

import asyncio
from typing import List
from fastapi import FastAPI, HTTPException
from app.agents.dispute_agent import draft_dispute_response
from app.agents.reconciliation_agent import investigate_discrepancy
from app.models.schemas import (
    ActionExecutionRequest,
    ActionExecutionResult,
    BatchInvestigationRequest,
    BatchInvestigationResult,
    DiscrepancyEvent,
    DisputeDraftResult,
    DisputeEvent,
    InvestigationResult,
)
from app.rag.knowledge_base import list_all_cases
from app.services.action_executor import (
    execute_guardrailed_action,
    get_execution_history,
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


@app.post("/agent/investigate/batch", response_model=BatchInvestigationResult)
async def run_batch_investigation(payload: BatchInvestigationRequest):
    results = await asyncio.gather(
        *(investigate_discrepancy(item) for item in payload.discrepancies)
    )
    auto_count = sum(1 for r in results if r.guardrail.auto_executable)
    return BatchInvestigationResult(
        total=len(results),
        auto_executable_count=auto_count,
        requires_approval_count=len(results) - auto_count,
        results=list(results),
    )


@app.post("/agent/disputes/draft", response_model=DisputeDraftResult)
async def run_dispute_draft(event: DisputeEvent):
    return await draft_dispute_response(event)


@app.post("/agent/actions/execute", response_model=ActionExecutionResult)
async def run_action_execution(req: ActionExecutionRequest):
    try:
        return await execute_guardrailed_action(req)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/agent/actions/history", response_model=List[ActionExecutionResult])
async def action_history():
    return get_execution_history()


@app.get("/agent/rag/cases")
async def rag_cases():
    return {"total": len(list_all_cases()), "cases": list_all_cases()}
