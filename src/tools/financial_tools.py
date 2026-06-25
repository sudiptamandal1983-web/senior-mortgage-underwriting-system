"""
src/tools/financial_tools.py
Deterministic financial calculations — no LLM involved.
All calculations with a correct answer use Python, not an LLM.
"""

from dataclasses import dataclass
from typing import Optional


# Dutch mortgage constants (AFM guidelines 2026)
MAX_DTI = 0.35              # maximum debt-to-income ratio
MAX_LTV_STANDARD = 0.90    # standard maximum LTV
MAX_LTV_NHG = 1.00         # NHG maximum LTV (100% including costs)
NHG_LIMIT_2026 = 435_000   # NHG guarantee limit in EUR
STRESS_RATE = 0.05          # AFM stress test rate
MIN_EMPLOYMENT_YEARS = 0.5  # minimum employment history


@dataclass
class DTIResult:
    dti_ratio: float
    monthly_debt_total: float
    gross_monthly_income: float
    passed: bool
    max_allowable_debt: float


@dataclass
class LTVResult:
    ltv_ratio: float
    loan_amount: float
    property_value: float
    passed: bool
    max_allowable_loan: float
    breach_reason: Optional[str]


@dataclass
class AffordabilityResult:
    passed: bool
    monthly_payment_estimated: float
    max_monthly_payment: float
    stress_payment: float
    reasoning: str


@dataclass
class MaxEligibleLoanResult:
    """
    Rogier use case: given an existing loan that causes LTV breach,
    calculate the maximum loan the applicant CAN take given their
    property value and existing obligations.
    """
    max_loan_by_ltv: float
    max_loan_by_dti: float
    max_loan_eligible: float
    existing_loan_balance: float
    property_value: float
    nhg_eligible: bool
    reasoning: str


def calculate_dti(
    gross_monthly_income: float,
    monthly_debt_obligations: float,
    existing_loan_monthly_payment: float,
    proposed_monthly_payment: float
) -> DTIResult:
    """
    Calculate debt-to-income ratio including existing and proposed obligations.
    DTI = total monthly debt / gross monthly income
    """
    total_monthly_debt = (
        monthly_debt_obligations +
        existing_loan_monthly_payment +
        proposed_monthly_payment
    )
    dti = total_monthly_debt / gross_monthly_income if gross_monthly_income > 0 else 1.0
    max_allowable = gross_monthly_income * MAX_DTI

    return DTIResult(
        dti_ratio=round(dti, 4),
        monthly_debt_total=round(total_monthly_debt, 2),
        gross_monthly_income=round(gross_monthly_income, 2),
        passed=dti <= MAX_DTI,
        max_allowable_debt=round(max_allowable, 2)
    )


def calculate_ltv(
    loan_amount: float,
    existing_loan_balance: float,
    property_value: float,
    nhg_requested: bool
) -> LTVResult:
    """
    Calculate loan-to-value ratio.
    Total secured debt (new loan + existing loan) / property value.
    This is the Rogier use case: existing loan balance increases effective LTV.
    """
    total_secured_debt = loan_amount + existing_loan_balance
    ltv = total_secured_debt / property_value if property_value > 0 else 1.0

    max_ltv = MAX_LTV_NHG if nhg_requested else MAX_LTV_STANDARD
    max_loan = (property_value * max_ltv) - existing_loan_balance

    breach_reason = None
    if ltv > max_ltv:
        if nhg_requested and loan_amount > NHG_LIMIT_2026:
            breach_reason = f"Loan amount EUR {loan_amount:,.0f} exceeds NHG limit of EUR {NHG_LIMIT_2026:,.0f}"
        elif existing_loan_balance > 0:
            breach_reason = (
                f"Existing loan balance of EUR {existing_loan_balance:,.0f} "
                f"brings combined LTV to {ltv:.1%}, exceeding the "
                f"{'NHG' if nhg_requested else 'standard'} limit of {max_ltv:.0%}"
            )
        else:
            breach_reason = f"Loan amount exceeds {max_ltv:.0%} LTV limit"

    return LTVResult(
        ltv_ratio=round(ltv, 4),
        loan_amount=round(loan_amount, 2),
        property_value=round(property_value, 2),
        passed=ltv <= max_ltv,
        max_allowable_loan=round(max(max_loan, 0), 2),
        breach_reason=breach_reason
    )


def estimate_monthly_payment(
    loan_amount: float,
    annual_rate: float = 0.04,
    term_years: int = 30
) -> float:
    """
    Estimate monthly annuity mortgage payment.
    Standard Dutch annuity formula.
    """
    if loan_amount <= 0:
        return 0.0
    monthly_rate = annual_rate / 12
    n_payments = term_years * 12
    if monthly_rate == 0:
        return loan_amount / n_payments
    payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** n_payments) / \
              ((1 + monthly_rate) ** n_payments - 1)
    return round(payment, 2)


def calculate_affordability(
    gross_monthly_income: float,
    monthly_debt_obligations: float,
    existing_loan_monthly_payment: float,
    loan_amount: float,
    term_years: int = 30
) -> AffordabilityResult:
    """
    AFM affordability check using stress rate.
    Monthly payment at stress rate must be affordable given income.
    """
    stress_payment = estimate_monthly_payment(loan_amount, STRESS_RATE, term_years)
    standard_payment = estimate_monthly_payment(loan_amount, 0.04, term_years)

    total_obligations = (
        monthly_debt_obligations +
        existing_loan_monthly_payment +
        stress_payment
    )
    max_monthly = gross_monthly_income * MAX_DTI

    passed = total_obligations <= max_monthly

    reasoning = (
        f"Stress-tested monthly payment at {STRESS_RATE:.0%}: EUR {stress_payment:,.0f}. "
        f"Total obligations (existing + proposed): EUR {total_obligations:,.0f}. "
        f"Maximum allowable at {MAX_DTI:.0%} DTI: EUR {max_monthly:,.0f}. "
        f"{'Passes' if passed else 'Fails'} affordability check."
    )

    return AffordabilityResult(
        passed=passed,
        monthly_payment_estimated=standard_payment,
        max_monthly_payment=max_monthly,
        stress_payment=stress_payment,
        reasoning=reasoning
    )


def calculate_max_eligible_loan(
    gross_monthly_income: float,
    monthly_debt_obligations: float,
    existing_loan_balance: float,
    existing_loan_monthly_payment: float,
    property_value: float,
    nhg_requested: bool,
    term_years: int = 30
) -> MaxEligibleLoanResult:
    """
    Rogier use case: existing loan leads to LTV breach on requested amount.
    Calculate what loan the applicant CAN take given:
    - LTV constraint (existing loan reduces headroom)
    - DTI constraint (income limits monthly payment capacity)
    Returns the lower of the two constraints as the max eligible loan.
    """
    # LTV constraint: how much headroom is left given existing loan?
    max_ltv = MAX_LTV_NHG if nhg_requested else MAX_LTV_STANDARD
    max_loan_by_ltv = max((property_value * max_ltv) - existing_loan_balance, 0)

    # DTI constraint: how much can income support?
    # Work backwards from max monthly payment to max loan amount
    available_for_new_loan = (gross_monthly_income * MAX_DTI) - monthly_debt_obligations - existing_loan_monthly_payment
    if available_for_new_loan <= 0:
        max_loan_by_dti = 0.0
    else:
        # Solve for loan amount given max monthly payment at stress rate
        monthly_rate = STRESS_RATE / 12
        n = term_years * 12
        max_loan_by_dti = available_for_new_loan * ((1 + monthly_rate) ** n - 1) / \
                          (monthly_rate * (1 + monthly_rate) ** n)

    max_loan_by_dti = round(max(max_loan_by_dti, 0), 2)
    max_loan_eligible = round(min(max_loan_by_ltv, max_loan_by_dti), 2)

    # NHG check
    nhg_eligible = (
        nhg_requested and
        max_loan_eligible <= NHG_LIMIT_2026 and
        property_value <= NHG_LIMIT_2026
    )

    reasoning = (
        f"Existing loan balance of EUR {existing_loan_balance:,.0f} reduces LTV headroom. "
        f"Maximum loan by LTV ({max_ltv:.0%} limit): EUR {max_loan_by_ltv:,.0f}. "
        f"Maximum loan by income (DTI {MAX_DTI:.0%} limit at {STRESS_RATE:.0%} stress rate): EUR {max_loan_by_dti:,.0f}. "
        f"Maximum eligible loan (lower of the two): EUR {max_loan_eligible:,.0f}. "
        f"{'NHG guarantee available' if nhg_eligible else 'NHG not available'} for this amount."
    )

    return MaxEligibleLoanResult(
        max_loan_by_ltv=round(max_loan_by_ltv, 2),
        max_loan_by_dti=max_loan_by_dti,
        max_loan_eligible=max_loan_eligible,
        existing_loan_balance=existing_loan_balance,
        property_value=property_value,
        nhg_eligible=nhg_eligible,
        reasoning=reasoning
    )
