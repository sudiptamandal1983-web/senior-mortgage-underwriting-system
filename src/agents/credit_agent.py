"""
src/agents/credit_agent.py
Credit assessment agent — deterministic financial calculations.
Includes Rogier use case: existing loan causing LTV breach,
calculates what loan the applicant CAN qualify for.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.agents.state import UnderwritingState
from src.tools.financial_tools import (
    calculate_dti, calculate_ltv, calculate_affordability,
    calculate_max_eligible_loan, estimate_monthly_payment
)
from datetime import datetime


def credit_agent(state: UnderwritingState) -> UnderwritingState:
    """
    Credit assessment agent.
    Runs DTI, LTV, and affordability checks deterministically.
    If LTV breach caused by existing loan, calculates max eligible alternative loan.
    """
    proposed_payment = estimate_monthly_payment(
        state["loan_amount_requested"],
        annual_rate=0.04,
        term_years=state["loan_term_years"]
    )

    # DTI calculation
    dti_result = calculate_dti(
        gross_monthly_income=state["gross_monthly_income"],
        monthly_debt_obligations=state["monthly_debt_obligations"],
        existing_loan_monthly_payment=state["existing_loan_monthly_payment"],
        proposed_monthly_payment=proposed_payment
    )

    # LTV calculation — includes existing loan balance
    ltv_result = calculate_ltv(
        loan_amount=state["loan_amount_requested"],
        existing_loan_balance=state["existing_loan_balance"],
        property_value=state["property_value"],
        nhg_requested=state["nhg_requested"]
    )

    # Affordability check
    affordability_result = calculate_affordability(
        gross_monthly_income=state["gross_monthly_income"],
        monthly_debt_obligations=state["monthly_debt_obligations"],
        existing_loan_monthly_payment=state["existing_loan_monthly_payment"],
        loan_amount=state["loan_amount_requested"],
        term_years=state["loan_term_years"]
    )

    # Rogier use case: LTV breach due to existing loan
    # Calculate what loan they CAN qualify for
    alternative_loan = None
    if not ltv_result.passed and state["existing_loan_balance"] > 0:
        max_eligible = calculate_max_eligible_loan(
            gross_monthly_income=state["gross_monthly_income"],
            monthly_debt_obligations=state["monthly_debt_obligations"],
            existing_loan_balance=state["existing_loan_balance"],
            existing_loan_monthly_payment=state["existing_loan_monthly_payment"],
            property_value=state["property_value"],
            nhg_requested=state["nhg_requested"],
            term_years=state["loan_term_years"]
        )

        if max_eligible.max_loan_eligible > 0:
            alternative_payment = estimate_monthly_payment(
                max_eligible.max_loan_eligible, 0.04, state["loan_term_years"]
            )
            alternative_loan = {
                "max_eligible_amount": max_eligible.max_loan_eligible,
                "limited_by": "ltv" if max_eligible.max_loan_by_ltv < max_eligible.max_loan_by_dti else "dti",
                "monthly_payment": alternative_payment,
                "nhg_eligible": max_eligible.nhg_eligible,
                "reasoning": max_eligible.reasoning,
                "shortfall": round(state["loan_amount_requested"] - max_eligible.max_loan_eligible, 2)
            }

    audit_entry = {
        "agent": "credit_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "dti_ratio": dti_result.dti_ratio,
        "dti_passed": dti_result.passed,
        "ltv_ratio": ltv_result.ltv_ratio,
        "ltv_passed": ltv_result.passed,
        "ltv_breach_reason": ltv_result.breach_reason,
        "affordability_passed": affordability_result.passed,
        "alternative_loan_calculated": alternative_loan is not None
    }

    return {
        **state,
        "dtia_ratio": dti_result.dti_ratio,
        "ltv_ratio": ltv_result.ltv_ratio,
        "affordability_passed": affordability_result.passed,
        "nhg_eligible": ltv_result.passed and state["nhg_requested"] and state["loan_amount_requested"] <= 435_000,
        "max_eligible_loan": ltv_result.max_allowable_loan,
        "ltv_breach_reason": ltv_result.breach_reason,
        "alternative_loan": alternative_loan,
        "audit_trail": [audit_entry]
    }
