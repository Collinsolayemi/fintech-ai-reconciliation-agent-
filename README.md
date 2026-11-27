# Autonomous FinTech Payment Reconciliation & Dispute Resolution Agent

An AI-powered investigation, root-cause analysis, and dispute-resolution microservice designed to pair with a double-entry core payment engine (such as `java fintech` / FintechCore).

> **Golden Rule:** The AI agent **never** performs financial math or directly mutates ledger balances. Deterministic code enforces accounting invariants ($\Sigma\text{Debits} = \Sigma\text{Credits}$), while the AI agent investigates unstructured evidence, identifies root causes, drafts chargeback rebuttals, and proposes strictly guardrailed actions for human-in-the-loop (HITL) approval.

---

## Core Capabilities

1. **Autonomous Reconciliation Investigation**
   - Receives unmatched/discrepancy items from a deterministic reconciliation job (e.g., missing webhook, FX/fee variance, duplicate payout, stuck escrow).
   - Uses **Tool Calling** to inspect internal ledger entries, gateway settlement records, and webhook delivery logs.
   - Outputs a structured root-cause diagnosis, confidence score, and recommended remediation.
2. **Chargeback & Dispute Evidence Drafting**
   - Correlates transaction history, KYC tier/status, IP/device metadata, and settlement proofs.
   - Drafts structured dispute rebuttal packets ready for Stripe/Paystack/card-network submission.
3. **RAG Memory (Past Cases & Bank Error Codes)**
   - Retrieves similar historical resolutions and bank/ISO-8583 error codes before making a decision.
4. **Financial Guardrails & Human-in-the-Loop (HITL)**
   - Enforces strict thresholds (`AUTO_RESOLVE_MAX_AMOUNT`, `MIN_CONFIDENCE_THRESHOLD`).
   - High-value or low-confidence cases are automatically routed to an admin approval queue.

---

## Project Structure

```text
fintech-ai-reconciliation-agent/
├── README.md                          # Project overview, setup, and concepts
├── .env.example                       # API keys, Ledger URL, and guardrail thresholds
├── pyproject.toml                     # Python dependencies & project metadata
├── docs/
│   └── ARCHITECTURE.md                # Agent loop, tool contracts, RAG & HITL design
├── app/
│   ├── main.py                        # FastAPI server & endpoints
│   ├── core/
│   │   ├── config.py                  # Environment configuration
│   │   └── guardrails.py              # Financial safety & HITL escalation rules
│   ├── models/
│   │   └── schemas.py                 # Pydantic request/response & audit schemas
│   ├── agents/
│   │   ├── reconciliation_agent.py    # Discrepancy root-cause investigator
│   │   └── dispute_agent.py           # Chargeback evidence drafter
│   ├── tools/
│   │   ├── ledger_tools.py            # Read-only tools for the Java Ledger API
│   │   └── gateway_tools.py           # Gateway settlement & webhook log tools
│   └── rag/
│       └── knowledge_base.py          # Historical resolutions & error-code retrieval
├── data/
│   └── sample_cases.json              # Sample discrepancy & dispute payloads
└── evals/
    └── test_scenarios.py              # Agent accuracy & guardrail evaluation suite
```

---

## Quick Start

### 1. Create a virtual environment & install dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure environment variables
```bash
cp .env.example .env
# Add your GEMINI_API_KEY (or LLM provider key) and LEDGER_API_URL
```

### 3. Run the FastAPI service
```bash
uvicorn app.main:app --reload --port 8090
```

### 4. Test an investigation
Once running, open **http://localhost:8090/docs** for interactive Swagger UI, or send a request using the payloads in `data/sample_cases.json`.

---

## Connecting to `java fintech` (FintechCore)
1. Start the Java Spring Boot ledger on `http://localhost:8080`.
2. Set `LEDGER_API_URL=http://localhost:8080/api/v1` in `.env`.
3. When `/admin/reconciliation/internal` or gateway settlement detects a discrepancy, forward the discrepancy payload to `POST http://localhost:8090/agent/investigate`.
