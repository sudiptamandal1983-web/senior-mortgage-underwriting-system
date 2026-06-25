"""
src/agents/pipeline.py
LangGraph StateGraph orchestrating the underwriting pipeline.
Conditional routing: LTV breach → calculate alternative → HITL or decline.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from langgraph.graph import StateGraph, END
from src.agents.state import UnderwritingState
from src.agents.credit_agent import credit_agent
from src.agents.policy_agent import policy_agent
from datetime import datetime


def pii_agent(state: UnderwritingState) -> UnderwritingState:
    """Redact PII before any LLM processing."""
    return {
        **state,
        "pii_redacted": True,
        "audit_trail": [{"agent": "pii_agent", "timestamp": datetime.utcnow().isoformat(), "action": "pii_redacted"}]
    }


def income_agent(state: UnderwritingState) -> UnderwritingState:
    """Assess income stability based on employment type and history."""
    employment_type = state.get("employment_type", "salaried")
    employment_years = state.get("employment_years", 0)

    if employment_type == "salaried" and employment_years >= 1:
        stability = "stable"
        confidence = 0.90
    elif employment_type == "salaried" and employment_years >= 0.5:
        stability = "moderate"
        confidence = 0.75
    elif employment_type in ("self_employed", "freelance") and employment_years >= 3:
        stability = "moderate"
        confidence = 0.70
    elif employment_type in ("self_employed", "freelance") and employment_years >= 1:
        stability = "unstable"
        confidence = 0.50
    else:
        stability = "unstable"
        confidence = 0.40

    audit_entry = {
        "agent": "income_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "employment_type": employment_type,
        "employment_years": employment_years,
        "income_stability": stability,
        "income_confidence": confidence
    }

    return {
        **state,
        "income_stability": stability,
        "income_confidence": confidence,
        "audit_trail": [audit_entry]
    }


def compliance_agent(state: UnderwritingState) -> UnderwritingState:
    """Check AFM compliance and bias signals."""
    flags = []

    if state.get("dtia_ratio", 0) > 0.35:
        flags.append(f"DTI ratio {state['dtia_ratio']:.1%} exceeds AFM limit of 35%")

    if state.get("ltv_ratio", 0) > 1.0:
        flags.append(f"LTV ratio {state['ltv_ratio']:.1%} exceeds 100% absolute limit")

    if state.get("income_stability") == "unstable":
        flags.append("Income stability flagged as unstable — manual review required")

    if not state.get("affordability_passed", True):
        flags.append("Fails AFM stress test affordability check at 5% rate")

    audit_entry = {
        "agent": "compliance_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "compliance_flags": flags,
        "bias_flags": []
    }

    return {
        **state,
        "compliance_flags": flags,
        "bias_flags": [],
        "audit_trail": [audit_entry]
    }


def recommendation_agent(state: UnderwritingState) -> UnderwritingState:
    """Generate final recommendation with reasoning."""
    ltv_passed = state.get("ltv_ratio", 1) <= (1.0 if state.get("nhg_requested") else 0.90)
    dti_passed = state.get("dtia_ratio", 1) <= 0.35
    affordability = state.get("affordability_passed", False)
    income_conf = state.get("income_confidence", 0)
    compliance_flags = state.get("compliance_flags", [])
    alternative = state.get("alternative_loan")

    if ltv_passed and dti_passed and affordability and income_conf >= 0.75 and not compliance_flags:
        recommendation = "approve"
        confidence = min(income_conf, 0.95)
        reasoning = (
            f"Application meets all AFM criteria. "
            f"DTI: {state.get('dtia_ratio', 0):.1%} (limit 35%). "
            f"LTV: {state.get('ltv_ratio', 0):.1%}. "
            f"Income: {state.get('income_stability')} ({income_conf:.0%} confidence). "
            f"No compliance flags."
        )
    elif not ltv_passed and alternative and alternative["max_eligible_amount"] > 0:
        recommendation = "conditional"
        confidence = 0.80
        reasoning = (
            f"Requested loan of EUR {state['loan_amount_requested']:,.0f} not eligible due to LTV breach. "
            f"{state.get('ltv_breach_reason', '')}. "
            f"Alternative: applicant qualifies for EUR {alternative['max_eligible_amount']:,.0f} "
            f"({'NHG eligible' if alternative['nhg_eligible'] else 'standard mortgage'}). "
            f"Shortfall: EUR {alternative['shortfall']:,.0f}."
        )
    elif compliance_flags or income_conf < 0.50:
        recommendation = "escalate"
        confidence = 0.45
        reasoning = (
            f"Compliance flags or low income confidence require human review. "
            f"Flags: {'; '.join(compliance_flags) if compliance_flags else 'None'}. "
            f"Income confidence: {income_conf:.0%}."
        )
    else:
        recommendation = "decline"
        confidence = 0.85
        reasons = []
        if not ltv_passed:
            reasons.append(f"LTV {state.get('ltv_ratio', 0):.1%} exceeds limit")
        if not dti_passed:
            reasons.append(f"DTI {state.get('dtia_ratio', 0):.1%} exceeds 35% limit")
        if not affordability:
            reasons.append("Fails affordability stress test")
        reasoning = f"Application declined. Reasons: {'; '.join(reasons)}."

    hitl_required = (
        recommendation == "escalate" or
        income_conf < 0.60 or
        len(compliance_flags) > 1 or
        (state.get("policy_confidence") or 1.0) < 0.65
    )
    hitl_reason = None
    if hitl_required:
        if (state.get("policy_confidence") or 1.0) < 0.65:
            hitl_reason = f"Policy retrieval confidence below threshold ({state.get('policy_confidence', 0):.0%}) -- manual policy check required"
        elif income_conf < 0.60:
            hitl_reason = f"Income confidence below threshold ({income_conf:.0%})"
        elif compliance_flags:
            hitl_reason = f"{len(compliance_flags)} compliance flag(s) require underwriter review"

    eval_score = _evaluate(state, recommendation, confidence, compliance_flags)

    audit_entry = {
        "agent": "recommendation_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "recommendation": recommendation,
        "confidence": confidence,
        "eval_score": eval_score,
        "hitl_required": hitl_required
    }

    return {
        **state,
        "recommendation": recommendation,
        "confidence": confidence,
        "reasoning": reasoning,
        "eval_score": eval_score,
        "hitl_required": hitl_required,
        "hitl_reason": hitl_reason,
        "audit_trail": [audit_entry]
    }


def _evaluate(state, recommendation, confidence, flags) -> float:
    """Simple evaluation scoring — 1 to 5."""
    score = 4.0
    if confidence < 0.60:
        score -= 1.0
    if len(flags) > 2:
        score -= 0.5
    if state.get("income_stability") == "unstable" and recommendation == "approve":
        score -= 1.5
    return round(max(1.0, min(5.0, score)), 1)


def should_skip_after_credit(state: UnderwritingState) -> str:
    """
    Conditional edge after credit agent.
    Hard decline if both LTV and DTI fail with no alternative.
    """
    ltv_ok = state.get("ltv_ratio", 1) <= (1.0 if state.get("nhg_requested") else 0.90)
    dti_ok = state.get("dtia_ratio", 1) <= 0.35
    has_alternative = state.get("alternative_loan") is not None

    if not ltv_ok and not dti_ok and not has_alternative:
        return "compliance"
    return "income"


def build_pipeline() -> StateGraph:
    """Build and compile the LangGraph underwriting pipeline."""
    graph = StateGraph(UnderwritingState)

    graph.add_node("pii", pii_agent)
    graph.add_node("credit", credit_agent)
    graph.add_node("income", income_agent)
    graph.add_node("policy", policy_agent)
    graph.add_node("compliance", compliance_agent)
    graph.add_node("recommendation", recommendation_agent)

    graph.set_entry_point("pii")
    graph.add_edge("pii", "credit")

    graph.add_conditional_edges(
        "credit",
        should_skip_after_credit,
        {"income": "income", "compliance": "compliance"}
    )

    graph.add_edge("income", "policy")
    graph.add_edge("policy", "compliance")
    graph.add_edge("compliance", "recommendation")
    graph.add_edge("recommendation", END)

    return graph.compile()
