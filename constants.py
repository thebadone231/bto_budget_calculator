"""
Singapore HDB BTO Flat Affordability Calculator - Constants

Official HDB loan parameters and CPF contribution rates.
Last updated: February 2026
"""

from datetime import date

# =============================================================================
# HDB LOAN PARAMETERS
# =============================================================================

# Interest rate: CPF OA rate (2.5%) + 0.1%
HDB_INTEREST_RATE = 0.026  # 2.6% per annum

# Maximum loan tenure
MAX_TENURE_YEARS = 25

# Loan-to-Value limit (as of Oct 2024 onwards)
LTV_LIMIT = 0.75  # 75% - means 25% downpayment required

# Mortgage Servicing Ratio - max % of gross income for mortgage
MSR_LIMIT = 0.30  # 30%

# HDB loan income ceiling (combined gross income)
HDB_INCOME_CEILING = 14000  # $14,000/month


# =============================================================================
# CPF CONTRIBUTION RATES (For Singapore Citizens, age 55 and below)
# =============================================================================

# CPF contribution rates by age bracket
# Format: (employee_rate, employer_rate, oa_rate, sa_rate, ma_rate)
CPF_RATES_BY_AGE = {
    # Age 55 and below
    (0, 35): {
        "employee": 0.20,
        "employer": 0.17,
        "total": 0.37,
        "oa": 0.23,  # 23% of gross wages to OA
        "sa": 0.06,
        "ma": 0.08,
    },
    (36, 45): {
        "employee": 0.20,
        "employer": 0.17,
        "total": 0.37,
        "oa": 0.21,
        "sa": 0.07,
        "ma": 0.09,
    },
    (46, 50): {
        "employee": 0.20,
        "employer": 0.17,
        "total": 0.37,
        "oa": 0.19,
        "sa": 0.08,
        "ma": 0.10,
    },
    (51, 55): {
        "employee": 0.20,
        "employer": 0.17,
        "total": 0.37,
        "oa": 0.15,
        "sa": 0.115,
        "ma": 0.105,
    },
    (56, 60): {
        "employee": 0.165,
        "employer": 0.145,
        "total": 0.31,
        "oa": 0.115,
        "sa": 0.095,
        "ma": 0.10,
    },
    (61, 65): {
        "employee": 0.115,
        "employer": 0.105,
        "total": 0.22,
        "oa": 0.035,
        "sa": 0.065,
        "ma": 0.12,
    },
    (66, 999): {
        "employee": 0.075,
        "employer": 0.075,
        "total": 0.15,
        "oa": 0.01,
        "sa": 0.01,
        "ma": 0.13,
    },
}


def get_cpf_rates(age: int) -> dict:
    """Get CPF contribution rates for a given age."""
    for (min_age, max_age), rates in CPF_RATES_BY_AGE.items():
        if min_age <= age <= max_age:
            return rates
    # Default to youngest bracket if age is somehow out of range
    return CPF_RATES_BY_AGE[(0, 35)]


# =============================================================================
# SINGAPORE FINANCIAL BENCHMARKS (for savings validation)
# Based on Department of Statistics Household Expenditure Survey
# =============================================================================

# Typical expense ratios as % of take-home pay by income bracket
EXPENSE_BENCHMARKS = {
    "low": {  # Gross income < $5,000
        "min_income": 0,
        "max_income": 5000,
        "typical_expense_ratio": 0.85,  # 85% of take-home on expenses
        "comfortable_savings_ratio": 0.15,
        "aggressive_savings_ratio": 0.25,
    },
    "mid_low": {  # Gross income $5,000 - $8,000
        "min_income": 5000,
        "max_income": 8000,
        "typical_expense_ratio": 0.75,
        "comfortable_savings_ratio": 0.20,
        "aggressive_savings_ratio": 0.35,
    },
    "mid": {  # Gross income $8,000 - $12,000
        "min_income": 8000,
        "max_income": 12000,
        "typical_expense_ratio": 0.65,
        "comfortable_savings_ratio": 0.25,
        "aggressive_savings_ratio": 0.40,
    },
    "high": {  # Gross income > $12,000
        "min_income": 12000,
        "max_income": float("inf"),
        "typical_expense_ratio": 0.55,
        "comfortable_savings_ratio": 0.30,
        "aggressive_savings_ratio": 0.45,
    },
}


def get_expense_benchmark(gross_income: float) -> dict:
    """Get expense benchmark for a given income level."""
    for _, benchmark in EXPENSE_BENCHMARKS.items():
        if benchmark["min_income"] <= gross_income < benchmark["max_income"]:
            return benchmark
    return EXPENSE_BENCHMARKS["high"]


# =============================================================================
# STAMP DUTY & LEGAL FEES
# =============================================================================

# Buyer's Stamp Duty (BSD) rates for residential property
# Effective from 15 Feb 2023 (Source: IRAS)
BSD_BRACKETS = [
    (180000, 0.01),      # First $180,000: 1%
    (180000, 0.02),      # Next $180,000: 2%
    (640000, 0.03),      # Next $640,000: 3%
    (float('inf'), 0.04) # Remaining amount: 4%
]

# HDB legal fee rates (per $1,000 of flat/loan amount)
# Source: HDB official documentation
LEGAL_FEE_TIERS = [
    (30000, 0.90),   # First $30,000: $0.90 per $1,000
    (30000, 0.72),   # Next $30,000: $0.72 per $1,000
    (float('inf'), 0.60)  # Remaining: $0.60 per $1,000
]

GST_RATE = 0.09  # 9% GST (as of 2024)


def calculate_hdb_legal_fees(amount: float) -> float:
    """
    Calculate HDB legal fees based on flat purchase price or loan amount.
    
    HDB legal fee structure:
    - First $30,000: $0.90 per $1,000
    - Next $30,000: $0.72 per $1,000
    - Remaining Amount: $0.60 per $1,000
    
    Fee is rounded up to next dollar before applying GST.
    Minimum fee is $21.80 (inclusive of GST).
    
    Args:
        amount: Purchase price or loan amount
        
    Returns:
        Legal fees including GST
    """
    if amount <= 0:
        return 0.0
    
    total_fee = 0.0
    remaining = amount
    
    for tier_amount, rate_per_1000 in LEGAL_FEE_TIERS:
        if remaining <= 0:
            break
        
        applicable_amount = min(remaining, tier_amount)
        # Calculate fee per $1,000
        total_fee += (applicable_amount / 1000) * rate_per_1000
        remaining -= applicable_amount
    
    # Round up to next dollar
    import math
    total_fee = math.ceil(total_fee)
    
    # Apply GST
    total_with_gst = total_fee * (1 + GST_RATE)
    
    # Ensure minimum fee
    min_fee = 21.80
    return max(min_fee, total_with_gst)


def calculate_stamp_duty(property_value: float) -> float:
    """
    Calculate Buyer's Stamp Duty (BSD) for residential property in Singapore.
    
    Uses tiered rates as per IRAS (effective from 15 Feb 2023):
    - First $180,000: 1%
    - Next $180,000: 2%
    - Next $640,000: 3%
    - Next $500,000: 4%
    - Next $1,500,000: 5%
    - Remaining amount: 6%
    
    Args:
        property_value: Purchase price of the property
        
    Returns:
        Stamp duty amount (rounded down to nearest dollar, minimum $1)
    """
    if property_value <= 0:
        return 0.0
    
    total_duty = 0.0
    remaining = property_value
    
    for bracket_amount, rate in BSD_BRACKETS:
        if remaining <= 0:
            break
        
        taxable_amount = min(remaining, bracket_amount)
        total_duty += taxable_amount * rate
        remaining -= taxable_amount
    
    # Round down to nearest dollar, minimum $1
    return max(1.0, float(int(total_duty)))


def calculate_total_upfront_cost(flat_price: float, loan_amount: float) -> tuple[float, float, float, float]:
    """
    Calculate total upfront cost for purchasing an HDB flat.
    
    Includes:
    1. Downpayment (25% of flat price)
    2. Stamp duty on Agreement for Lease (based on flat price)
    3. Legal fee for purchase (based on flat price)
    4. Legal fee for mortgage (based on loan amount)
    
    Args:
        flat_price: Purchase price of the flat
        loan_amount: HDB housing loan amount
        
    Returns:
        Tuple of (total_upfront, downpayment, stamp_duty, total_legal_fees)
    """
    downpayment = flat_price * 0.25
    stamp_duty = calculate_stamp_duty(flat_price)
    legal_fee_purchase = calculate_hdb_legal_fees(flat_price)
    legal_fee_mortgage = calculate_hdb_legal_fees(loan_amount)
    total_legal_fees = legal_fee_purchase + legal_fee_mortgage
    
    total_upfront = downpayment + stamp_duty + total_legal_fees
    
    return total_upfront, downpayment, stamp_duty, total_legal_fees


# =============================================================================
# DEFAULT VALUES FOR UI
# =============================================================================

DEFAULTS = {
    "applicant_1_age": 26,
    "applicant_2_age": 24,
    "applicant_1_income": 5300,
    "applicant_2_income": 5300,
    # Work start dates (None = currently working, or date(year, month, day) for specific start date)
    "applicant_1_work_start_date": None,  # Currently working
    "applicant_2_work_start_date": date(2026, 5, 1),  # Starts May 1, 2026
    # Per-applicant financial commitments
    "applicant_1_credit_card": 0,
    "applicant_1_car_loan": 0,
    "applicant_1_other_loans": 0,
    "applicant_2_credit_card": 0,
    "applicant_2_car_loan": 0,
    "applicant_2_other_loans": 0,
    # Per-applicant savings
    "applicant_1_cpf_oa": 10800,
    "applicant_1_cash": 12600,
    "applicant_1_monthly_cash_savings": 1800,
    "applicant_2_cpf_oa": 0,
    "applicant_2_cash": 0,
    "applicant_2_monthly_cash_savings": 1800,
    # Target flat
    "target_flat_price": 800000,
}

# Flat price range for slider
FLAT_PRICE_MIN = 200000
FLAT_PRICE_MAX = 1000000
FLAT_PRICE_STEP = 10000

# Income range for slider
INCOME_MIN = 0
INCOME_MAX = 14000
INCOME_STEP = 100
