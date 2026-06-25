# Senior Mortgage Underwriting System (SMUS)

A production-architecture multi-agent AI system for mortgage underwriting decision support. Built with LangGraph, FastAPI, and deterministic financial tools — designed for Dutch regulatory compliance, explainability, and human-in-the-loop oversight.

---

## What this is

Mortgage underwriting is a domain where the stakes of AI decisions are asymmetric: a wrong approval and a wrong rejection do not cost the same thing. That asymmetry should shape the architecture from the start — not sit in a policy document somewhere.

This system demonstrates how agentic AI can support underwriting decisions in a regulated environment: handling structured assessment at scale, surfacing relevant policy context, calculating alternative loan eligibility when a requested loan is not possible, and routing edge cases to human review rather than pushing low-confidence decisions through automatically.

---

## Key use case — existing loan causing LTV breach

A common scenario in Dutch mortgage practice: an applicant has an existing loan secured against the same property. The combined debt (existing loan + requested new loan) exceeds the AFM LTV limit, making the requested amount ineligible.

Rather than a simple decline, the system calculates the maximum loan the applicant **can** qualify for, given two constraints applied simultaneously:

**LTV constraint** — how much headroom remains given the existing loan balance and property value?

```
Max loan by LTV = (property value × LTV limit) − existing loan balance
```

**DTI constraint** — how much can the applicant's income support at the AFM stress rate?

```
Available monthly capacity = (gross income × 35% DTI limit) − existing obligations
Max loan by DTI = solve annuity formula for loan amount at this monthly capacity
```

The system returns the **lower of the two** as the maximum eligible loan, with a clear explanation of which constraint is binding and the shortfall against the requested amount.

**Example response for an LTV breach scenario:**

```json
{
  "application_id": "DEMO-002",
  "recommendation": "conditional",
  "confidence": 0.80,
  "reasoning": "Requested loan of EUR 200,000 not eligible due to LTV breach. Existing loan balance of EUR 130,000 brings combined LTV to 94.3%, exceeding the standard limit of 90%. Alternative: applicant qualifies for EUR 85,000 (standard mortgage). Shortfall: EUR 115,000.",
  "ltv_ratio": 0.943,
  "alternative_loan": {
    "max_eligible_amount": 85000.0,
    "limited_by": "ltv",
    "monthly_payment": 406.0,
    "nhg_eligible": false,
    "shortfall": 115000.0,
    "reasoning": "Existing loan balance of EUR 130,000 reduces LTV headroom. Maximum loan by LTV (90% limit): EUR 85,000. Maximum loan by income (35% DTI at 5% stress rate): EUR 142,000. Maximum eligible loan (lower of the two): EUR 85,000."
  }
}
```

---

## Architecture

Five specialist agents coordinate through a LangGraph StateGraph. All state passes through a typed schema — no agent calls another directly.

```
Application intake (FastAPI)
        ↓
PII Sanitisation Agent       — redacts sensitive fields before any LLM processing
        ↓
Credit Assessment Agent      — deterministic DTI, LTV, affordability
                               + alternative loan calculation for LTV breach
        ↓ (conditional edge)
Income Verification Agent    — employment type, stability, confidence scoring
        ↓
Compliance Agent             — AFM guidelines, bias signals, regulatory flags
        ↓
Recommendation Agent         — approve / conditional / escalate / decline
                               + evaluation scoring + HITL routing
        ↓
FastAPI response with full audit trail
```

### Conditional routing

If the Credit agent finds that both LTV and DTI fail with no viable alternative loan, the pipeline skips Income verification and routes directly to Compliance — avoiding unnecessary processing for a case that will decline regardless.

### Key design decisions

**Deterministic tools for all financial calculations.** DTI ratio, LTV, affordability, and the alternative loan calculation are implemented as deterministic Python functions — not LLM calls. There is a correct answer to these calculations. An LLM introduces unnecessary variance and occasional confident wrong answers. Python does not.

**PII sanitisation before any LLM processing.** Applicant names, identifiers, and personal data are tokenised before data reaches any LLM endpoint. Non-negotiable in a GDPR-regulated environment.

**Confidence-based HITL escalation.** Cases below the confidence threshold, or flagged by the compliance agent, route to a human reviewer rather than auto-approving. The reviewer sees the assembled reasoning — what the system found and why it was uncertain — not a blank case to re-assess from scratch.

**Audit trail for every decision.** Every agent output, confidence score, routing decision, and timestamp is logged in a structured, append-only audit trail. Reconstructable for regulatory review.

**EU AI Act alignment.** Mortgage credit decisioning is likely high-risk under Annex III of the EU AI Act. The HITL gate, audit trail, and explainability layer are designed to meet the human oversight and transparency requirements that apply to high-risk AI systems.

---

## Agent detail

| Agent | Calculation type | Primary output |
|---|---|---|
| PII Sanitisation | Deterministic | Redacted application record |
| Credit Assessment | Deterministic Python tools | DTI, LTV, affordability, alternative loan |
| Income Verification | Rule-based scoring | Stability assessment + confidence score |
| Compliance | Rule-based + AFM rules | Compliance flags, bias checks |
| Recommendation | Deterministic routing | Recommendation + confidence + HITL decision |

---

## Cloud deployment architecture

Designed for Azure deployment with full managed identity authentication — no hardcoded credentials.

```
Internet / Internal network
        ↓
Azure API Management (rate limiting, authentication)
        ↓
Azure Container Apps (FastAPI — SMUS service)
        ├── Azure OpenAI (GPT-4o) — Managed Identity auth
        ├── Azure AI Search — vector index for policy documents
        └── Azure Key Vault — secrets at runtime
        ↓
Azure Monitor + Log Analytics
        ├── Escalation rate (leading indicator for model degradation)
        ├── Confidence score distribution
        ├── HITL routing rate
        └── Audit trail logging
```

### Azure components

- **Azure Container Apps** — hosts the FastAPI underwriting service, auto-scales, no cluster management
- **Azure OpenAI (GPT-4o)** — LLM for income interpretation and narrative generation
- **Azure AI Search** — managed vector index for policy document retrieval (replaces local ChromaDB in production)
- **Azure Key Vault** — API keys and connection strings retrieved at runtime
- **Managed Identity** — service-to-service authentication, no secrets in environment variables or code
- **Azure Monitor + Log Analytics** — AI-specific metrics: escalation rate, confidence score distribution, HITL routing rate, audit trail

### Monitoring — key metrics

| Metric | Alert threshold | Why it matters |
|---|---|---|
| HITL escalation rate | Above baseline + 2 std dev | Leading indicator — rises before complaints |
| Confidence score mean | Below 3.2 | Signals model or retrieval degradation |
| LTV breach rate | Tracked, no threshold | Business signal for product fit |
| Alternative loan acceptance | Tracked | Measures value of Rogier use case |

---

## Tech stack

- **Orchestration** — LangGraph (StateGraph, typed state schema, conditional edges)
- **API** — FastAPI with Pydantic request/response validation
- **Containerisation** — Docker, docker-compose for local development
- **Financial tools** — deterministic Python for all calculations (DTI, LTV, affordability, max eligible loan)
- **Compliance** — Dutch AFM mortgage guidelines 2026, NHG guarantee conditions, EU AI Act alignment
- **Authentication** — API key (local), Azure Managed Identity (production)

---

## Project structure

```
senior-mortgage-underwriting-system/
├── src/
│   ├── api/
│   │   └── main.py              # FastAPI application — 4 scenarios including Rogier use case
│   ├── agents/
│   │   ├── state.py             # TypedDict state schema
│   │   ├── pipeline.py          # LangGraph StateGraph with conditional routing
│   │   └── credit_agent.py      # Credit assessment + alternative loan calculation
│   ├── tools/
│   │   └── financial_tools.py   # Deterministic DTI, LTV, affordability, max eligible loan
│   ├── rag/
│   │   └── policy_retrieval.py  # ChromaDB RAG for Dutch mortgage policy documents
│   └── compliance/
│       └── dutch_mortgage.py    # AFM guidelines and regulatory checks
├── data/
│   ├── sample_applications/     # 4 synthetic Dutch mortgage scenarios
│   └── policy_documents/        # Dutch mortgage policy documents
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Local setup

### Prerequisites
- Python 3.10+
- Docker (optional, for containerised run)

### Run locally with Python

```bash
git clone https://github.com/sudiptamandal1983-web/senior-mortgage-underwriting-system.git
cd senior-mortgage-underwriting-system

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

uvicorn src.api.main:app --reload --port 8000
```

### Run with Docker

```bash
docker-compose up --build
```

### API documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Sample scenarios: `http://localhost:8000/scenarios`

---

## Sample API calls

### Standard assessment

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-local" \
  -d '{
    "application_id": "APP-2026-001",
    "applicant_age": 32,
    "gross_monthly_income": 6000,
    "monthly_debt_obligations": 200,
    "loan_amount_requested": 320000,
    "property_value": 400000,
    "existing_loan_balance": 0,
    "existing_loan_monthly_payment": 0,
    "loan_term_years": 30,
    "employment_type": "salaried",
    "employment_years": 4,
    "nhg_requested": false
  }'
```

### Rogier use case — existing loan causing LTV breach

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key-local" \
  -d '{
    "application_id": "APP-2026-002",
    "applicant_age": 42,
    "gross_monthly_income": 5500,
    "monthly_debt_obligations": 300,
    "loan_amount_requested": 200000,
    "property_value": 350000,
    "existing_loan_balance": 130000,
    "existing_loan_monthly_payment": 700,
    "loan_term_years": 20,
    "employment_type": "salaried",
    "employment_years": 8,
    "nhg_requested": false
  }'
```

---

## Status

Production-architecture demonstration with working LangGraph pipeline and FastAPI layer. Azure deployment requires connection to Azure OpenAI, Azure AI Search, and Key Vault — configuration documented in the deployment architecture section above.

---

## Related projects

- [Portfolio RCA Intelligence System](https://github.com/sudiptamandal1983-web/portfolio-rca) — anomaly detection across 890k loan records with quality-gated LLM evaluation
- [CircularFlow](https://github.com/sudiptamandal1983-web/circularflow) — multi-agent returns routing with HITL evaluation gate
- [Autonomous Financial Research Analyst](https://github.com/sudiptamandal1983-web/Autonomous-Financial-Research-Analyst) — agentic RAG for investment research
