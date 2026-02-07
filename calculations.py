"""
Singapore HDB BTO Flat Affordability Calculator - Calculations

Core financial calculations for HDB loan eligibility, CPF projections,
and affordability analysis.
"""

from dataclasses import dataclass
from typing import Optional

from constants import (
    HDB_INTEREST_RATE,
    MAX_TENURE_YEARS,
    LTV_LIMIT,
    MSR_LIMIT,
    HDB_INCOME_CEILING,
    get_cpf_rates,
    get_expense_benchmark,
    calculate_stamp_duty,
    calculate_hdb_legal_fees,
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
