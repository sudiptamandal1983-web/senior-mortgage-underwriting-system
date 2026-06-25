"""
src/api/main.py
FastAPI application for the Senior Mortgage Underwriting System.
Cloud-native API layer for Azure Container Apps deployment.
"""

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from typing import Optional, List
import json
import os
import logging
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agents.pipeline import build_pipeline
from src.agents.state import UnderwritingState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Senior Mortgage Underwriting System (SMUS)",
    description=(
        "Agentic AI underwriting decision support for Dutch mortgages. "
        "LangGraph multi-agent pipeline with AFM compliance, HITL escalation, "
        "and alternative loan calculation for LTV breach scenarios."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"]
)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    expected = os.getenv("SMUS_API_KEY", "dev-key-local")
    if api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


class UnderwritingRequest(BaseModel):
    application_id: str = Field(..., example="APP-2026-001")
    applicant_age: int = Field(..., ge=18, le=80, example=35)
    gross_monthly_income: float = Field(..., gt=0, example=5500.0,
        description="Gross monthly income in EUR")
    monthly_debt_obligations: float = Field(default=0.0, ge=0, example=300.0,
        description="Existing monthly debt obligations excluding mortgage in EUR")
    loan_amount_requested: float = Field(..., gt=0, example=350000.0,
        description="Requested new mortgage amount in EUR")
    property_value: float = Field(..., gt=0, example=400000.0,
        description="Appraised property value in EUR")
    existing_loan_balance: float = Field(default=0.0, ge=0, example=120000.0,
        description="Existing mortgage/loan balance on the same property in EUR. "
                    "This is the Rogier use case: an existing loan reduces LTV headroom "
                    "and may cause the requested loan to be ineligible.")
    existing_loan_monthly_payment: float = Field(default=0.0, ge=0, example=650.0,
        description="Monthly payment on existing loan in EUR")
    loan_term_years: int = Field(default=30, ge=5, le=40, example=30)
    employment_type: str = Field(default="salaried",
        example="salaried",
        description="salaried / self_employed / freelance")
    employment_years: float = Field(default=2.0, ge=0, example=3.5)
    nhg_requested: bool = Field(default=False, example=False,
        description="Whether NHG guarantee is requested (max loan EUR 435,000)")
    income_documents: List[str] = Field(
        default=["salary_slip_3months", "employment_contract"],
        example=["salary_slip_3months", "employment_contract"]
    )

    @validator("employment_type")
    def validate_employment_type(cls, v):
        allowed = ["salaried", "self_employed", "freelance"]
        if v not in allowed:
            raise ValueError(f"employment_type must be one of {allowed}")
        return v


class AlternativeLoan(BaseModel):
    max_eligible_amount: float
    limited_by: str
    monthly_payment: float
    nhg_eligible: bool
    shortfall: float
    reasoning: str


class UnderwritingResponse(BaseModel):
    application_id: str
    recommendation: str
    confidence: float
    reasoning: str
    dtia_ratio: Optional[float]
    ltv_ratio: Optional[float]
    affordability_passed: Optional[bool]
    nhg_eligible: Optional[bool]
    income_stability: Optional[str]
    compliance_flags: Optional[List[str]]
    alternative_loan: Optional[AlternativeLoan]
    eval_score: Optional[float]
    hitl_required: Optional[bool]
    hitl_reason: Optional[str]
    processed_at: str
    audit_entries: int


pipeline = build_pipeline()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "SMUS", "version": "1.0.0"}


@app.post("/assess", response_model=UnderwritingResponse)
async def assess_application(
    request: UnderwritingRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Assess a mortgage application through the full LangGraph pipeline.

    Key feature: if an existing loan causes LTV breach on the requested amount,
    the system automatically calculates the maximum loan the applicant CAN qualify for,
    given their property value (LTV constraint) and income (DTI constraint).
    The lower of the two constraints is returned as the alternative loan amount.
    """
    logger.info(f"Processing application {request.application_id}")

    initial_state: UnderwritingState = {
        "application_id": request.application_id,
        "applicant_age": request.applicant_age,
        "gross_monthly_income": request.gross_monthly_income,
        "monthly_debt_obligations": request.monthly_debt_obligations,
        "loan_amount_requested": request.loan_amount_requested,
        "property_value": request.property_value,
        "existing_loan_balance": request.existing_loan_balance,
        "existing_loan_monthly_payment": request.existing_loan_monthly_payment,
        "loan_term_years": request.loan_term_years,
        "employment_type": request.employment_type,
        "employment_years": request.employment_years,
        "nhg_requested": request.nhg_requested,
        "income_documents": request.income_documents,
        "pii_redacted": False,
        "dtia_ratio": None,
        "ltv_ratio": None,
        "affordability_passed": None,
        "nhg_eligible": None,
        "max_eligible_loan": None,
        "ltv_breach_reason": None,
        "income_stability": None,
        "income_confidence": None,
        "policy_chunks": None,
        "policy_confidence": None,
        "compliance_flags": None,
        "bias_flags": None,
        "recommendation": None,
        "confidence": None,
        "reasoning": None,
        "alternative_loan": None,
        "eval_score": None,
        "hitl_required": None,
        "hitl_reason": None,
        "audit_trail": [],
        "retry_count": 0
    }

    try:
        result = pipeline.invoke(initial_state)
    except Exception as e:
        logger.error(f"Pipeline error for {request.application_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    alt = result.get("alternative_loan")
    alt_model = None
    if alt:
        alt_model = AlternativeLoan(
            max_eligible_amount=alt["max_eligible_amount"],
            limited_by=alt["limited_by"],
            monthly_payment=alt["monthly_payment"],
            nhg_eligible=alt["nhg_eligible"],
            shortfall=alt["shortfall"],
            reasoning=alt["reasoning"]
        )

    logger.info(
        f"Application {request.application_id}: "
        f"{result.get('recommendation')} "
        f"(confidence {result.get('confidence', 0):.0%})"
    )

    return UnderwritingResponse(
        application_id=result["application_id"],
        recommendation=result.get("recommendation", "error"),
        confidence=result.get("confidence", 0.0),
        reasoning=result.get("reasoning", ""),
        dtia_ratio=result.get("dtia_ratio"),
        ltv_ratio=result.get("ltv_ratio"),
        affordability_passed=result.get("affordability_passed"),
        nhg_eligible=result.get("nhg_eligible"),
        income_stability=result.get("income_stability"),
        compliance_flags=result.get("compliance_flags", []),
        alternative_loan=alt_model,
        eval_score=result.get("eval_score"),
        hitl_required=result.get("hitl_required", False),
        hitl_reason=result.get("hitl_reason"),
        processed_at=datetime.utcnow().isoformat(),
        audit_entries=len(result.get("audit_trail", []))
    )


@app.get("/scenarios")
async def get_scenarios():
    """Return sample scenarios including the Rogier LTV use case."""
    return {
        "scenarios": [
            {
                "name": "Standard approval",
                "description": "Straightforward salaried applicant, no existing loan",
                "application_id": "DEMO-001",
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
                "nhg_requested": False,
                "income_documents": ["salary_slip_3months", "employment_contract"]
            },
            {
                "name": "LTV breach — existing loan (Rogier use case)",
                "description": (
                    "Applicant has existing loan balance on the property. "
                    "Requested new loan exceeds LTV limit. "
                    "System calculates maximum eligible alternative loan."
                ),
                "application_id": "DEMO-002",
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
                "nhg_requested": False,
                "income_documents": ["salary_slip_3months", "employment_contract"]
            },
            {
                "name": "NHG application",
                "description": "First-time buyer requesting NHG guarantee",
                "application_id": "DEMO-003",
                "applicant_age": 28,
                "gross_monthly_income": 4200,
                "monthly_debt_obligations": 0,
                "loan_amount_requested": 280000,
                "property_value": 295000,
                "existing_loan_balance": 0,
                "existing_loan_monthly_payment": 0,
                "loan_term_years": 30,
                "employment_type": "salaried",
                "employment_years": 1.5,
                "nhg_requested": True,
                "income_documents": ["salary_slip_3months", "employment_contract"]
            },
            {
                "name": "Self-employed — HITL escalation",
                "description": "Self-employed applicant with short history — routes to human review",
                "application_id": "DEMO-004",
                "applicant_age": 38,
                "gross_monthly_income": 7000,
                "monthly_debt_obligations": 500,
                "loan_amount_requested": 380000,
                "property_value": 500000,
                "existing_loan_balance": 0,
                "existing_loan_monthly_payment": 0,
                "loan_term_years": 25,
                "employment_type": "self_employed",
                "employment_years": 1.5,
                "nhg_requested": False,
                "income_documents": ["tax_return_2years", "accountant_statement"]
            }
        ]
    }
