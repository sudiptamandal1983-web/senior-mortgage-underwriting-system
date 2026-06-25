"""
src/agents/state.py
Typed state schema carrying application data through the LangGraph pipeline.
"""

from typing import TypedDict, Optional, List, Annotated
import operator


class UnderwritingState(TypedDict):
    # Input application data
    application_id: str
    applicant_age: int
    gross_monthly_income: float
    monthly_debt_obligations: float
    loan_amount_requested: float
    property_value: float
    existing_loan_balance: float        # Rogier use case: existing loan
    existing_loan_monthly_payment: float
    loan_term_years: int
    employment_type: str                # salaried / self_employed / freelance
    employment_years: float
    nhg_requested: bool
    income_documents: List[str]         # list of document descriptions

    # PII redaction flag
    pii_redacted: bool

    # Agent outputs
    dtia_ratio: Optional[float]         # debt-to-income
    ltv_ratio: Optional[float]          # loan-to-value
    affordability_passed: Optional[bool]
    nhg_eligible: Optional[bool]
    max_eligible_loan: Optional[float]  # Rogier use case: what CAN they borrow?
    ltv_breach_reason: Optional[str]    # why LTV fails

    income_stability: Optional[str]     # stable / moderate / unstable
    income_confidence: Optional[float]

    policy_chunks: Optional[List[str]]
    policy_confidence: Optional[float]

    compliance_flags: Optional[List[str]]
    bias_flags: Optional[List[str]]

    recommendation: Optional[str]       # approve / conditional / decline / escalate
    confidence: Optional[float]
    reasoning: Optional[str]
    alternative_loan: Optional[dict]    # Rogier use case: alternative product

    eval_score: Optional[float]
    hitl_required: Optional[bool]
    hitl_reason: Optional[str]

    audit_trail: Annotated[List[dict], operator.add]
    retry_count: int
