"""
Singapore HDB BTO Flat Affordability Calculator - Calculations

Core financial calculations for HDB loan eligibility, CPF projections,
and affordability analysis.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta

from constants import (
    HDB_INTEREST_RATE,
    MAX_TENURE_YEARS,
    LTV_LIMIT,
    MSR_LIMIT,
    HDB_INCOME_CEILING,
    PAYMENT_SCHEMES,
    get_cpf_rates,
    get_expense_benchmark,
    calculate_stamp_duty,
    calculate_hdb_legal_fees,
    get_ehg_amount,
)


@dataclass
class LoanEligibility:
    """Result of loan eligibility calculation."""
    max_monthly_installment: float
    max_loan_amount: float
    max_flat_price: float
    tenure_years: int
    interest_rate: float
    available_msr: float
    total_commitments: float
    exceeds_income_ceiling: bool


@dataclass
class AffordabilityResult:
    """Result of affordability calculation at a specific point in time."""
    target_flat_price: float
    stamp_duty: float
    legal_fees: float
    total_cost: float  # flat_price + stamp_duty + legal_fees
    required_downpayment: float  # 25% of flat + stamp duty + legal fees
    loan_amount: float  # 75% of flat price (banks only loan on flat value)
    projected_cpf_oa: float
    projected_cash: float
    total_available: float
    downpayment_gap: float  # Positive = shortfall, Negative = surplus
    can_afford_downpayment: bool
    can_afford_loan: bool  # Within loan eligibility
    can_afford: bool  # Overall
    monthly_payment: float


@dataclass
class TenureAnalysis:
    """Analysis of a specific loan tenure."""
    tenure_years: int
    monthly_payment: float
    total_interest: float
    total_cost: float
    interest_saved_vs_max: float
    is_affordable: bool
    msr_buffer: float  # Amount below MSR limit


@dataclass
class SavingsHealthCheck:
    """Assessment of savings rate sustainability."""
    savings_ratio: float  # As % of take-home
    status: str  # "healthy", "aggressive", "unsustainable"
    message: str
    suggested_savings: float
    take_home_income: float


@dataclass
class TimingAnalysisPoint:
    """A single point in the EHG vs loan timing analysis."""
    application_date: date
    assessed_income: float
    ehg_amount: int
    max_hdb_loan: float
    loan_needed: float
    loan_shortfall: float   # max(0, loan_needed - max_hdb_loan)
    cash_needed: float      # flat_price - max_hdb_loan - ehg + stamp_duty + legal_fees
    ehg_eligible: bool      # whether 12-month employment (14 months before application) requirement is met


@dataclass
class LeaseSigningAllocation:
    """Per-applicant CPF/cash split at lease signing."""
    cpf_contrib_1: float
    cash_contrib_1: float
    cpf_contrib_2: float
    cash_contrib_2: float
    shortfall: float
    months_to_close_shortfall: float


@dataclass
class PaymentPhaseBreakdown:
    """Phased downpayment breakdown for a BTO purchase."""
    scheme: str
    scheme_label: str
    flat_price: float
    lease_signing_pct: float
    lease_signing_downpayment: float
    lease_signing_stamp_duty: float
    lease_signing_legal_fees: float
    lease_signing_total: float
    key_collection_pct: float
    key_collection_downpayment: float
    key_collection_loan_shortfall: float
    key_collection_ehg_offset: float
    key_collection_total: float
    actual_loan: float
    total_upfront: float


# =============================================================================
# LOAN CALCULATIONS
# =============================================================================

def calculate_monthly_payment(
    loan_amount: float,
    annual_rate: float = HDB_INTEREST_RATE,
    tenure_years: int = MAX_TENURE_YEARS
) -> float:
    """
    Calculate monthly mortgage payment using PMT formula.
    
    PMT = P * [r(1+r)^n] / [(1+r)^n - 1]
    where:
        P = Principal (loan amount)
        r = Monthly interest rate
        n = Number of months
    """
    if loan_amount <= 0:
        return 0.0
    
    r = annual_rate / 12  # Monthly rate
    n = tenure_years * 12  # Total months
    
    if r == 0:
        return loan_amount / n
    
    return loan_amount * (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def calculate_max_loan(
    monthly_installment: float,
    annual_rate: float = HDB_INTEREST_RATE,
    tenure_years: int = MAX_TENURE_YEARS
) -> float:
    """
    Calculate maximum loan amount given a monthly payment limit.
    
    This is the inverse of PMT - Present Value of Annuity.
    PV = PMT * [(1+r)^n - 1] / [r(1+r)^n]
    """
    if monthly_installment <= 0:
        return 0.0
    
    r = annual_rate / 12
    n = tenure_years * 12
    
    if r == 0:
        return monthly_installment * n
    
    return monthly_installment * ((1 + r) ** n - 1) / (r * (1 + r) ** n)


def calculate_total_interest(
    loan_amount: float,
    annual_rate: float = HDB_INTEREST_RATE,
    tenure_years: int = MAX_TENURE_YEARS
) -> float:
    """Calculate total interest paid over the loan tenure."""
    monthly = calculate_monthly_payment(loan_amount, annual_rate, tenure_years)
    total_paid = monthly * tenure_years * 12
    return total_paid - loan_amount


def calculate_required_downpayment(flat_price: float) -> float:
    """Calculate minimum downpayment required (25% for HDB loan)."""
    return flat_price * (1 - LTV_LIMIT)


def calculate_loan_amount(flat_price: float) -> float:
    """Calculate loan amount based on LTV (75% of flat price)."""
    return flat_price * LTV_LIMIT


def calculate_loan_eligibility(
    gross_income: float,
    credit_card_payment: float = 0,
    car_loan_payment: float = 0,
    other_loan_payment: float = 0,
    tenure_years: int = MAX_TENURE_YEARS,
    interest_rate: float = HDB_INTEREST_RATE
) -> LoanEligibility:
    """
    Calculate maximum HDB loan eligibility.
    
    Takes into account:
    - MSR limit (30% of gross income)
    - Existing financial commitments
    - HDB income ceiling
    """
    # Check income ceiling
    exceeds_ceiling = gross_income > HDB_INCOME_CEILING
    
    # Calculate available MSR after existing commitments
    total_commitments = credit_card_payment + car_loan_payment + other_loan_payment
    max_msr = gross_income * MSR_LIMIT
    available_msr = max(0, max_msr - total_commitments)
    
    # Calculate max loan based on available MSR
    max_loan = calculate_max_loan(available_msr, interest_rate, tenure_years)
    
    # Calculate max flat price based on LTV
    max_flat_price = max_loan / LTV_LIMIT if LTV_LIMIT > 0 else 0
    
    return LoanEligibility(
        max_monthly_installment=available_msr,
        max_loan_amount=max_loan,
        max_flat_price=max_flat_price,
        tenure_years=tenure_years,
        interest_rate=interest_rate,
        available_msr=available_msr,
        total_commitments=total_commitments,
        exceeds_income_ceiling=exceeds_ceiling,
    )


# =============================================================================
# CPF PROJECTIONS
# =============================================================================

def calculate_monthly_cpf_oa(gross_income: float, age: int) -> float:
    """
    Calculate monthly CPF OA contribution based on income and age.
    
    Note: This is based on the OA allocation rate for the given age bracket.
    """
    rates = get_cpf_rates(age)
    return gross_income * rates["oa"]


def calculate_combined_monthly_cpf_oa(
    income_1: float,
    age_1: int,
    income_2: float,
    age_2: int
) -> float:
    """Calculate combined monthly CPF OA contribution for both applicants."""
    oa_1 = calculate_monthly_cpf_oa(income_1, age_1)
    oa_2 = calculate_monthly_cpf_oa(income_2, age_2)
    return oa_1 + oa_2


def project_cpf_oa_balance(
    current_balance: float,
    monthly_contribution: float,
    months: int
) -> float:
    """
    Project CPF OA balance after a number of months.
    
    Note: This is a simplified projection that doesn't account for:
    - CPF OA interest (currently 2.5% p.a.)
    - Salary increments
    - CPF contribution changes with age
    
    For a more accurate projection, these could be added in the future.
    """
    return current_balance + (monthly_contribution * months)


def project_cpf_oa_with_interest(
    current_balance: float,
    monthly_contribution: float,
    months: int,
    annual_interest_rate: float = 0.025  # CPF OA rate
) -> float:
    """
    Project CPF OA balance with interest compounding.
    
    CPF interest is computed monthly and credited annually, but we simplify
    to monthly compounding for projection purposes.
    """
    balance = current_balance
    monthly_rate = annual_interest_rate / 12
    
    for _ in range(months):
        balance = balance * (1 + monthly_rate) + monthly_contribution
    
    return balance


# =============================================================================
# CASH PROJECTIONS
# =============================================================================

def project_cash_balance(
    current_balance: float,
    monthly_savings: float,
    months: int
) -> float:
    """Project cash savings balance after a number of months."""
    return current_balance + (monthly_savings * months)


# =============================================================================
# AFFORDABILITY ANALYSIS
# =============================================================================

def calculate_affordability(
    target_flat_price: float,
    loan_eligibility: LoanEligibility,
    projected_cpf_oa: float,
    projected_cash: float
) -> AffordabilityResult:
    """
    Calculate whether the target flat is affordable.
    
    Total upfront cost includes:
    - 25% downpayment on flat price
    - Stamp duty (based on flat price)
    - Legal fee for purchase (based on flat price)
    - Legal fee for mortgage (based on loan amount)
    
    Loan amount = 75% of flat price
    
    Checks:
    1. Is the loan amount within eligibility?
    2. Is there enough for upfront costs (CPF + Cash)?
    """
    # Loan is 75% of flat price
    loan_amount = calculate_loan_amount(target_flat_price)
    
    # Calculate all costs
    stamp_duty = calculate_stamp_duty(target_flat_price)
    legal_fee_purchase = calculate_hdb_legal_fees(target_flat_price)
    legal_fee_mortgage = calculate_hdb_legal_fees(loan_amount)
    total_legal_fees = legal_fee_purchase + legal_fee_mortgage
    
    # 25% downpayment on flat price
    downpayment_on_flat = calculate_required_downpayment(target_flat_price)
    
    # Total required upfront = downpayment + stamp duty + both legal fees
    required_downpayment = downpayment_on_flat + stamp_duty + total_legal_fees
    
    # Total cost = flat price + stamp duty + legal fees
    total_cost = target_flat_price + stamp_duty + total_legal_fees
    
    total_available = projected_cpf_oa + projected_cash
    downpayment_gap = required_downpayment - total_available
    
    can_afford_downpayment = total_available >= required_downpayment
    can_afford_loan = loan_amount <= loan_eligibility.max_loan_amount
    
    monthly_payment = calculate_monthly_payment(
        loan_amount,
        loan_eligibility.interest_rate,
        loan_eligibility.tenure_years
    )
    
    return AffordabilityResult(
        target_flat_price=target_flat_price,
        stamp_duty=stamp_duty,
        legal_fees=total_legal_fees,
        total_cost=total_cost,
        required_downpayment=required_downpayment,
        loan_amount=loan_amount,
        projected_cpf_oa=projected_cpf_oa,
        projected_cash=projected_cash,
        total_available=total_available,
        downpayment_gap=downpayment_gap,
        can_afford_downpayment=can_afford_downpayment,
        can_afford_loan=can_afford_loan,
        can_afford=can_afford_downpayment and can_afford_loan,
        monthly_payment=monthly_payment,
    )


def calculate_payment_phases(
    flat_price: float,
    scheme: str,
    actual_loan: float,
    ehg_grant: float = 0,
) -> PaymentPhaseBreakdown:
    """
    Break down the 25% downpayment into lease-signing and key-collection phases.

    Stamp duty and legal fees are due at lease signing (Agreement for Lease).
    Any loan shortfall is due at key collection.
    """
    scheme_info = PAYMENT_SCHEMES[scheme]
    lease_signing_pct = scheme_info["lease_signing_pct"]
    key_collection_pct = scheme_info["key_collection_pct"]

    lease_signing_dp = flat_price * lease_signing_pct
    stamp_duty = calculate_stamp_duty(flat_price)
    legal_fee_purchase = calculate_hdb_legal_fees(flat_price)
    legal_fee_mortgage = calculate_hdb_legal_fees(actual_loan)
    legal_fees = legal_fee_purchase + legal_fee_mortgage
    lease_signing_total = lease_signing_dp + stamp_duty + legal_fees

    key_collection_dp = flat_price * key_collection_pct
    loan_shortfall = max(0.0, flat_price * LTV_LIMIT - actual_loan)
    key_collection_total = key_collection_dp + loan_shortfall - ehg_grant

    return PaymentPhaseBreakdown(
        scheme=scheme,
        scheme_label=scheme_info["label"],
        flat_price=flat_price,
        lease_signing_pct=lease_signing_pct,
        lease_signing_downpayment=lease_signing_dp,
        lease_signing_stamp_duty=stamp_duty,
        lease_signing_legal_fees=legal_fees,
        lease_signing_total=lease_signing_total,
        key_collection_pct=key_collection_pct,
        key_collection_downpayment=key_collection_dp,
        key_collection_loan_shortfall=loan_shortfall,
        key_collection_ehg_offset=ehg_grant,
        key_collection_total=key_collection_total,
        actual_loan=actual_loan,
        total_upfront=lease_signing_total + key_collection_total,
    )


def calculate_max_affordable_flat(
    loan_eligibility: LoanEligibility,
    available_downpayment: float
) -> float:
    """
    Calculate the maximum flat price that can be afforded.
    
    Limited by whichever is lower:
    1. Max flat based on loan eligibility (loan / 0.75)
    2. Max flat based on available downpayment (iterative due to stamp duty and legal fee tiers)
    
    Note: available_downpayment must cover: 25% downpayment + stamp duty + legal fees (purchase + mortgage)
    """
    max_from_loan = loan_eligibility.max_flat_price
    
    # Iteratively find max flat price from available downpayment
    # Since stamp duty and legal fees have tiers, we use binary search
    low, high = 0.0, max_from_loan * 2  # Upper bound
    tolerance = 100  # Within $100
    
    max_from_downpayment = 0.0
    
    for _ in range(50):  # Max iterations
        mid = (low + high) / 2
        
        # Calculate required upfront for this flat price
        loan_amt = mid * LTV_LIMIT  # 75% loan
        downpayment_on_flat = mid * (1 - LTV_LIMIT)  # 25% downpayment
        stamp_duty = calculate_stamp_duty(mid)
        legal_fee_purchase = calculate_hdb_legal_fees(mid)
        legal_fee_mortgage = calculate_hdb_legal_fees(loan_amt)
        
        required_upfront = downpayment_on_flat + stamp_duty + legal_fee_purchase + legal_fee_mortgage
        
        if abs(required_upfront - available_downpayment) < tolerance:
            max_from_downpayment = mid
            break
        elif required_upfront > available_downpayment:
            high = mid
        else:
            low = mid
            max_from_downpayment = mid  # Keep best valid result
    
    return min(max_from_loan, max_from_downpayment)


# =============================================================================
# TENURE OPTIMIZATION
# =============================================================================

def analyze_tenure(
    loan_amount: float,
    tenure_years: int,
    max_monthly_payment: float,
    interest_rate: float = HDB_INTEREST_RATE
) -> TenureAnalysis:
    """Analyze a specific loan tenure."""
    monthly = calculate_monthly_payment(loan_amount, interest_rate, tenure_years)
    total_interest = calculate_total_interest(loan_amount, interest_rate, tenure_years)
    total_cost = loan_amount + total_interest
    
    # Compare to max tenure (25 years)
    interest_at_max = calculate_total_interest(loan_amount, interest_rate, MAX_TENURE_YEARS)
    interest_saved = interest_at_max - total_interest
    
    is_affordable = monthly <= max_monthly_payment
    msr_buffer = max_monthly_payment - monthly
    
    return TenureAnalysis(
        tenure_years=tenure_years,
        monthly_payment=monthly,
        total_interest=total_interest,
        total_cost=total_cost,
        interest_saved_vs_max=interest_saved,
        is_affordable=is_affordable,
        msr_buffer=msr_buffer,
    )


def find_optimal_tenure(
    loan_amount: float,
    max_monthly_payment: float,
    comfort_buffer: float = 0,
    interest_rate: float = HDB_INTEREST_RATE,
    min_tenure: int = 5,
    max_tenure: int = MAX_TENURE_YEARS
) -> Optional[TenureAnalysis]:
    """
    Find the shortest affordable tenure.
    
    Args:
        loan_amount: The loan principal
        max_monthly_payment: Maximum monthly payment (MSR-based)
        comfort_buffer: Additional buffer below max payment for comfort
        interest_rate: Annual interest rate
        min_tenure: Minimum tenure to consider
        max_tenure: Maximum tenure to consider
    
    Returns:
        TenureAnalysis for optimal tenure, or None if no tenure is affordable
    """
    effective_max = max_monthly_payment - comfort_buffer
    
    for tenure in range(min_tenure, max_tenure + 1):
        analysis = analyze_tenure(loan_amount, tenure, effective_max, interest_rate)
        if analysis.is_affordable:
            return analysis
    
    return None


def generate_tenure_comparison(
    loan_amount: float,
    max_monthly_payment: float,
    interest_rate: float = HDB_INTEREST_RATE
) -> list[TenureAnalysis]:
    """Generate comparison of all tenures from 5 to 25 years."""
    return [
        analyze_tenure(loan_amount, tenure, max_monthly_payment, interest_rate)
        for tenure in range(5, MAX_TENURE_YEARS + 1)
    ]


# =============================================================================
# SAVINGS HEALTH CHECK
# =============================================================================

def check_savings_health(
    gross_income: float,
    monthly_savings: float
) -> SavingsHealthCheck:
    """
    Assess if the savings rate is sustainable.
    
    Based on Singapore household expenditure benchmarks.
    """
    # Calculate take-home (after CPF employee contribution of ~20%)
    employee_cpf = gross_income * 0.20  # Simplified - actual varies by age
    take_home = gross_income - employee_cpf
    
    if take_home <= 0:
        return SavingsHealthCheck(
            savings_ratio=0,
            status="invalid",
            message="Invalid income entered",
            suggested_savings=0,
            take_home_income=0,
        )
    
    savings_ratio = monthly_savings / take_home
    benchmark = get_expense_benchmark(gross_income)
    
    # Determine status
    if savings_ratio > 0.50:
        status = "unsustainable"
        message = (
            f"🔴 Very aggressive - saving {savings_ratio:.0%} of take-home. "
            "This is likely unsustainable long-term. Consider a more realistic target."
        )
    elif savings_ratio > benchmark["aggressive_savings_ratio"]:
        status = "aggressive"
        message = (
            f"🟡 Aggressive - saving {savings_ratio:.0%} of take-home. "
            "This may be challenging to maintain. Ensure you have an emergency fund."
        )
    elif savings_ratio >= benchmark["comfortable_savings_ratio"]:
        status = "healthy"
        message = (
            f"🟢 Healthy - saving {savings_ratio:.0%} of take-home. "
            "This is a sustainable savings rate for your income level."
        )
    elif savings_ratio > 0:
        status = "low"
        message = (
            f"ℹ️ Conservative - saving {savings_ratio:.0%} of take-home. "
            "Consider if you can increase savings to reach your housing goals faster."
        )
    else:
        status = "none"
        message = "⚠️ No savings configured. Add monthly savings to project your affordability."
    
    suggested = take_home * benchmark["comfortable_savings_ratio"]
    
    return SavingsHealthCheck(
        savings_ratio=savings_ratio,
        status=status,
        message=message,
        suggested_savings=suggested,
        take_home_income=take_home,
    )


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def months_between_dates(start_date, end_date) -> int:
    """Calculate number of months between two dates."""
    return (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)


def format_currency(amount: float) -> str:
    """Format amount as Singapore dollars."""
    if amount >= 0:
        return f"${amount:,.0f}"
    else:
        return f"-${abs(amount):,.0f}"


# =============================================================================
# EHG VS LOAN TIMING ANALYSIS
# =============================================================================

def calculate_assessed_income(
    income_1: float,
    income_2: float,
    work_start_1: date,
    work_start_2: date,
    application_date: date,
) -> float:
    """
    Calculate HDB-assessed combined monthly income.

    HDB uses a 12-month average over the window [application_date - 14m, application_date - 3m].
    Months where an applicant hadn't started work yet contribute $0.
    """
    window_start = application_date - relativedelta(months=14)
    total = 0.0
    for i in range(12):
        month = window_start + relativedelta(months=i)
        if work_start_1 <= month:
            total += income_1
        if work_start_2 <= month:
            total += income_2
    return total / 12


def calculate_ehg_eligible_date(work_start_1: date, work_start_2: date) -> date:
    """
    Return the earliest application date where at least one applicant satisfies
    the EHG employment requirement: 12 months of work completed at least 2 months
    before the application date (i.e. work_start + 14 months <= application_date).
    """
    return min(work_start_1, work_start_2) + relativedelta(months=14)


def generate_timing_series(
    income_1: float,
    income_2: float,
    work_start_1: date,
    work_start_2: date,
    target_flat_price: float,
    start_month: date,
    num_months: int,
    credit_card: float = 0,
    car_loan: float = 0,
    other_loans: float = 0,
    dia: bool = False,
) -> list[TimingAnalysisPoint]:
    """
    Generate a TimingAnalysisPoint for each month from start_month to
    start_month + num_months, showing the EHG grant vs loan trade-off.

    When dia=True, income is assessed 36 months after the application date
    (Deferred Income Assessment).
    """
    ehg_eligible_date = calculate_ehg_eligible_date(work_start_1, work_start_2)
    loan_needed = target_flat_price * LTV_LIMIT
    stamp_duty = calculate_stamp_duty(target_flat_price)
    legal_fee_purchase = calculate_hdb_legal_fees(target_flat_price)

    series = []
    for i in range(num_months + 1):
        application_date = start_month + relativedelta(months=i)

        assessment_date = application_date + relativedelta(months=36) if dia else application_date
        assessed_income = calculate_assessed_income(
            income_1, income_2, work_start_1, work_start_2, assessment_date
        )

        ehg_eligible = application_date >= ehg_eligible_date and assessed_income < 9000
        ehg_amount = get_ehg_amount(assessed_income) if ehg_eligible else 0

        eligibility = calculate_loan_eligibility(
            gross_income=assessed_income,
            credit_card_payment=credit_card,
            car_loan_payment=car_loan,
            other_loan_payment=other_loans,
        )

        if eligibility.exceeds_income_ceiling:
            max_hdb_loan = 0.0
        else:
            max_hdb_loan = min(eligibility.max_loan_amount, loan_needed)

        loan_shortfall = max(0.0, loan_needed - max_hdb_loan)
        legal_fees = legal_fee_purchase + calculate_hdb_legal_fees(max_hdb_loan)
        cash_needed = target_flat_price - max_hdb_loan - ehg_amount + stamp_duty + legal_fees

        series.append(TimingAnalysisPoint(
            application_date=application_date,
            assessed_income=assessed_income,
            ehg_amount=ehg_amount,
            max_hdb_loan=max_hdb_loan,
            loan_needed=loan_needed,
            loan_shortfall=loan_shortfall,
            cash_needed=cash_needed,
            ehg_eligible=ehg_eligible,
        ))

    return series


def allocate_lease_signing_payment(
    amount_needed: float,
    cpf_1: float,
    cpf_2: float,
    cash_1: float,
    cash_2: float,
    monthly_combined_savings: float,
) -> LeaseSigningAllocation:
    """
    Split the lease-signing amount between two applicants using a CPF-first,
    equal-split-with-spillover algorithm.

    Step 1: CPF equal split, each covers up to half.
    Step 2: CPF spillover — if one is short, the other's surplus CPF covers the gap.
    Step 3: Cash equal split of whatever remains.
    Step 4: Cash spillover — same pattern.
    Step 5: Compute shortfall and months-to-close.
    """
    import math

    remaining = amount_needed

    # Step 1 & 2: CPF
    target_each = remaining / 2
    cpf_c1 = min(cpf_1, target_each)
    cpf_c2 = min(cpf_2, target_each)
    remaining -= cpf_c1 + cpf_c2

    # CPF spillover
    if remaining > 0:
        extra = min(cpf_1 - cpf_c1, remaining)
        cpf_c1 += extra
        remaining -= extra
    if remaining > 0:
        extra = min(cpf_2 - cpf_c2, remaining)
        cpf_c2 += extra
        remaining -= extra

    # Step 3 & 4: Cash
    cash_c1 = cash_c2 = 0.0
    if remaining > 0:
        target_each = remaining / 2
        cash_c1 = min(cash_1, target_each)
        cash_c2 = min(cash_2, target_each)
        remaining -= cash_c1 + cash_c2

    # Cash spillover
    if remaining > 0:
        extra = min(cash_1 - cash_c1, remaining)
        cash_c1 += extra
        remaining -= extra
    if remaining > 0:
        extra = min(cash_2 - cash_c2, remaining)
        cash_c2 += extra
        remaining -= extra

    shortfall = max(0.0, remaining)
    months_to_close = (
        math.ceil(shortfall / monthly_combined_savings)
        if shortfall > 0 and monthly_combined_savings > 0
        else 0.0
    )

    return LeaseSigningAllocation(
        cpf_contrib_1=cpf_c1,
        cash_contrib_1=cash_c1,
        cpf_contrib_2=cpf_c2,
        cash_contrib_2=cash_c2,
        shortfall=shortfall,
        months_to_close_shortfall=months_to_close,
    )
