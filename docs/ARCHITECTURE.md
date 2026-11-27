# Architecture: Autonomous Reconciliation & Dispute Resolution Agent

## 1. End-to-End Flow

```text
[Java Ledger / Gateway Webhook]
        │
        ▼  (1) Discrepancy or Dispute Event
[POST /agent/investigate]
        │
        ▼  (2) Retrieve similar past cases (RAG)
[Knowledge Base (pgvector / JSON)]
        │
        ▼  (3) Iterative Investigation Loop (LLM + Read-Only Tools)
  ├── get_ledger_entries(reference)
  ├── get_gateway_settlement(reference, provider)
  └── get_webhook_logs(reference)
        │
        ▼  (4) Structured Diagnosis + Proposed Action
[Guardrail Policy Engine]
  ├── confidence >= 0.90 AND amount <= $100  ──▶  Eligible for Auto-Action (e.g. Replay Webhook)
  └── otherwise                              ──▶  Queue for Human-in-the-Loop (HITL) Approval
```

## 2. Why This Architecture Is Safe for FinTech
- **Zero Direct Balance Mutation:** The agent has no SQL write access and no tool that directly updates account balances.
- **Deterministic Validation:** Every proposed adjustment must still pass the core ledger's double-entry validation ($\Sigma\text{Debits} = \Sigma\text{Credits}$).
- **Full Auditability:** Every tool call, retrieved RAG context, and reasoning summary is recorded in `audit_trail` for compliance review.

## 3. Evaluation Strategy (`evals/`)
Before deploying any prompt or model change:
1. Run `pytest evals/test_scenarios.py`.
2. Verify **Root-Cause Accuracy** across known failure modes (dropped webhook, FX fee variance, duplicate settlement, friendly fraud).
3. Verify **Guardrail Compliance** (0% auto-execution on high-value or low-confidence cases).
