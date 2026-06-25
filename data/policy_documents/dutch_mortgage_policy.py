"""
data/policy_documents/dutch_mortgage_policy.py
Synthetic Dutch mortgage policy documents based on publicly available
AFM guidelines and NHG conditions for 2026.
Used as the corpus for ChromaDB RAG retrieval.
"""

POLICY_DOCUMENTS = [
    {
        "id": "afm-ltv-001",
        "title": "AFM LTV Limits 2026",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "Loan-to-Value (LTV) limits for Dutch mortgages are set by the AFM under "
            "the Mortgage Credit Directive. For standard mortgages without NHG guarantee, "
            "the maximum LTV is 90% of the property value. This means the total secured "
            "debt on a property — including any existing mortgage balance — may not exceed "
            "90% of the appraised value. For mortgages with NHG (Nationale Hypotheek Garantie) "
            "guarantee, the maximum LTV is 100% including costs, subject to the NHG loan limit "
            "of EUR 435,000 for 2026. When an applicant has an existing loan secured against "
            "the same property, the combined outstanding balance of both the existing loan and "
            "the new mortgage must remain within the applicable LTV limit."
        )
    },
    {
        "id": "afm-dti-001",
        "title": "AFM DTI and Income Requirements 2026",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "Debt-to-income (DTI) limits restrict the proportion of gross monthly income "
            "that may be committed to debt service obligations. The maximum DTI ratio for "
            "Dutch mortgages is 35% of gross monthly income. This includes all existing debt "
            "obligations — personal loans, credit card debt, existing mortgage payments — "
            "plus the proposed new mortgage payment. The affordability assessment must be "
            "conducted using a stress test interest rate of 5% per annum, regardless of the "
            "actual mortgage rate offered. If the monthly payment at the stress rate would "
            "cause total obligations to exceed 35% of gross income, the mortgage is not "
            "eligible under responsible lending guidelines."
        )
    },
    {
        "id": "nhg-001",
        "title": "NHG Guarantee Conditions 2026",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "The Nationale Hypotheek Garantie (NHG) provides a guarantee for mortgage loans "
            "up to EUR 435,000 in 2026. To be eligible for NHG, the property must be the "
            "applicant's primary residence in the Netherlands. The mortgage must be an annuity "
            "or linear repayment mortgage. Interest-only mortgages are not eligible for NHG. "
            "The property value must not exceed EUR 435,000. NHG allows a maximum LTV of 100% "
            "including purchase costs such as transfer tax and notary fees. The NHG guarantee "
            "fee (risicobijdrage) is 0.6% of the mortgage amount in 2026, payable at inception. "
            "NHG provides protection for the lender in case of involuntary sale at a loss."
        )
    },
    {
        "id": "afm-income-001",
        "title": "AFM Income Verification Requirements",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "Income verification for mortgage applications requires documentation appropriate "
            "to the applicant's employment type. For salaried employees, a minimum of three "
            "months of recent salary slips and a current employment contract or employer "
            "statement are required. The employment must have been in place for at least "
            "six months. For self-employed applicants and freelancers, a minimum of three "
            "years of tax returns (aangifte inkomstenbelasting) and an accountant statement "
            "are required. Income from self-employment is calculated as the average of the "
            "last three years. For applicants with less than three years of self-employment "
            "history, additional documentation and manual underwriter review are required. "
            "Temporary employment contracts require an employer's intention statement "
            "(intentieverklaring) confirming the expectation of continued employment."
        )
    },
    {
        "id": "afm-existing-loan-001",
        "title": "AFM Guidelines for Applicants with Existing Mortgage Obligations",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "When an applicant holds an existing mortgage or loan secured against the same "
            "property, the combined LTV of the existing balance plus the new loan must not "
            "exceed the applicable LTV limit. The existing loan monthly payment must be "
            "included in the DTI calculation alongside the proposed new loan payment. "
            "If the combined LTV would exceed the limit, the lender must calculate the "
            "maximum eligible loan amount — defined as the lower of: (a) the LTV headroom "
            "remaining after the existing loan balance (property value times LTV limit minus "
            "existing balance), and (b) the maximum loan supportable by the applicant's "
            "income under the DTI limit at the stress test rate. The applicant must be "
            "informed of the maximum eligible amount and the reason for the reduction. "
            "This maximum eligible amount calculation must be documented in the underwriting "
            "record and included in any regulatory audit trail."
        )
    },
    {
        "id": "eu-ai-act-001",
        "title": "EU AI Act Requirements for Mortgage Credit Decisioning",
        "effective_date": "2026-08-01",
        "version": "2026.1",
        "content": (
            "Automated systems used in mortgage credit assessment are classified as high-risk "
            "AI systems under Annex III of the EU AI Act. This classification applies to any "
            "AI system that materially influences a credit decision affecting a natural person. "
            "High-risk AI systems in credit decisioning must meet the following requirements: "
            "meaningful human oversight before decisions take effect; transparency to applicants "
            "about the use of automated decision-making; accuracy and robustness requirements "
            "including bias monitoring across protected characteristic groups; technical "
            "documentation sufficient for regulatory audit; and an audit trail logging all "
            "material steps in the decision process. Applicants have the right under GDPR "
            "Article 22 to request human review of any automated decision that significantly "
            "affects them. Lenders must be able to explain the logic of any automated "
            "underwriting decision in plain language on request."
        )
    },
    {
        "id": "afm-bias-001",
        "title": "AFM Responsible Lending and Non-Discrimination Requirements",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "Dutch mortgage lenders are required under the Wet gelijke behandeling and EU "
            "Mortgage Credit Directive to ensure that lending decisions do not discriminate "
            "on the basis of protected characteristics including age, gender, nationality, "
            "marital status, or disability. Automated underwriting systems must be monitored "
            "for differential impact across these groups. Where an automated system produces "
            "systematically different outcomes for protected groups without objective "
            "justification based on credit risk factors, the system must be reviewed and "
            "corrected. Lenders must maintain records sufficient to demonstrate non-discriminatory "
            "lending practice to the AFM on request. Annual bias monitoring reports are "
            "recommended for institutions using automated credit decisioning systems."
        )
    },
    {
        "id": "afm-hitl-001",
        "title": "AFM Human Oversight Requirements for Automated Underwriting",
        "effective_date": "2026-01-01",
        "version": "2026.1",
        "content": (
            "The AFM requires that automated mortgage underwriting systems include meaningful "
            "human oversight for decisions that significantly affect applicants. Meaningful "
            "oversight means that a qualified human underwriter reviews the automated "
            "assessment and has the authority to override it before the decision is "
            "communicated to the applicant. The human reviewer must have access to the "
            "reasoning behind the automated recommendation, including the key factors that "
            "drove the decision. Rubber-stamping of automated outputs without genuine review "
            "does not constitute meaningful oversight. Cases involving unusual income "
            "structures, existing loan complications, or policy edge cases should be "
            "automatically escalated to human review regardless of the automated confidence "
            "score. The escalation criteria and override rates must be logged and available "
            "for regulatory inspection."
        )
    }
]
