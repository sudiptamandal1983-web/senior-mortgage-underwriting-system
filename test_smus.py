import sys
import requests

BASE = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json", "X-API-Key": "dev-key-local"}

def test(name, payload, expected, alt=False, hitl=False):
    try:
        r = requests.post(f"{BASE}/assess", json=payload, headers=HEADERS, timeout=30).json()
    except Exception as e:
        print(f"\nFAIL {name}: {e}")
        return False
    ok = (r.get("recommendation") == expected
          and (not alt or r.get("alternative_loan") is not None)
          and (not hitl or r.get("hitl_required") is True))
    print(f"\n{'PASS' if ok else 'FAIL'} {name}")
    print(f"  recommendation: {r.get('recommendation')} | ltv: {r.get('ltv_ratio',0):.1%} | hitl: {r.get('hitl_required')}")
    if r.get("alternative_loan"):
        a = r["alternative_loan"]
        print(f"  alternative: EUR {a['max_eligible_amount']:,.0f} limited by {a['limited_by']}")
    return ok

print("=== SMUS TEST SUITE ===")
results = []

try:
    r = requests.get(f"{BASE}/health", timeout=10).json()
    ok = r.get("status") == "healthy"
    results.append(ok)
    print(f"\n{'PASS' if ok else 'FAIL'} Health check {r}")
except Exception as e:
    print(f"\nFAIL Health: {e}")
    results.append(False)

results.append(test("Test 1 Standard approval",
    {"application_id": "T1", "applicant_age": 32, "gross_monthly_income": 6000,
     "monthly_debt_obligations": 200, "loan_amount_requested": 320000,
     "property_value": 400000, "existing_loan_balance": 0,
     "existing_loan_monthly_payment": 0, "loan_term_years": 30,
     "employment_type": "salaried", "employment_years": 4, "nhg_requested": False},
    "approve"))

results.append(test("Test 2 Rogier LTV breach",
    {"application_id": "T2", "applicant_age": 42, "gross_monthly_income": 5500,
     "monthly_debt_obligations": 300, "loan_amount_requested": 200000,
     "property_value": 350000, "existing_loan_balance": 130000,
     "existing_loan_monthly_payment": 700, "loan_term_years": 20,
     "employment_type": "salaried", "employment_years": 8, "nhg_requested": False},
    "conditional", alt=True))

results.append(test("Test 3 NHG application",
    {"application_id": "T3", "applicant_age": 28, "gross_monthly_income": 4200,
     "monthly_debt_obligations": 0, "loan_amount_requested": 250000,
     "property_value": 320000, "existing_loan_balance": 0,
     "existing_loan_monthly_payment": 0, "loan_term_years": 30,
     "employment_type": "salaried", "employment_years": 3,
     "nhg_requested": True},
    "approve"))

results.append(test("Test 4 Self-employed HITL",
    {"application_id": "T4", "applicant_age": 38, "gross_monthly_income": 7000,
     "monthly_debt_obligations": 500, "loan_amount_requested": 380000,
     "property_value": 500000, "existing_loan_balance": 0,
     "existing_loan_monthly_payment": 0, "loan_term_years": 25,
     "employment_type": "self_employed", "employment_years": 1.5, "nhg_requested": False},
    "escalate", hitl=True))

print(f"\n{'='*40}")
print(f"RESULTS: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)