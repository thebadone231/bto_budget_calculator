"""
Singapore HDB BTO Flat Affordability Calculator

A Streamlit app to help couples determine what BTO flats they can afford
based on their income, savings, and financial commitments.

Features:
- Loan eligibility calculation (30% MSR limit, 25% downpayment)
- CPF OA savings projection with 2.5% interest
- Tenure optimization
- What-if analysis

Run with: streamlit run main.py
"""

import streamlit as st
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd

from constants import (
    DEFAULTS,
    FLAT_PRICE_MIN,
    FLAT_PRICE_MAX,
    FLAT_PRICE_STEP,
    INCOME_MIN,
    INCOME_MAX,
    INCOME_STEP,
    HDB_INTEREST_RATE,
    MAX_TENURE_YEARS,
    LTV_LIMIT,
    MSR_LIMIT,
    HDB_INCOME_CEILING,
    get_cpf_rates,
    calculate_stamp_duty,
    calculate_hdb_legal_fees,
)

from calculations import (
    calculate_loan_eligibility,
    calculate_monthly_cpf_oa,
    calculate_combined_monthly_cpf_oa,
    project_cpf_oa_balance,
    project_cpf_oa_with_interest,
    project_cash_balance,
    calculate_affordability,
    calculate_max_affordable_flat,
    calculate_monthly_payment,
    calculate_total_interest,
    calculate_required_downpayment,
    calculate_loan_amount,
    find_optimal_tenure,
    generate_tenure_comparison,
    check_savings_health,
    months_between_dates,
    format_currency,
)

from charts import (
    create_savings_projection_chart,
    create_tenure_comparison_chart,
    create_affordability_breakdown_chart,
    create_msr_allocation_chart,
    create_max_affordable_over_time_chart,
    create_tenure_table_data,
)


# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="BTO Affordability Calculator",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_effective_working_months(
    work_start_date: date,
    completion_date: date,
    today: date
) -> int:
    """
    Calculate how many months an applicant will be working between now and completion.
    
    - If they've already started working: full duration from now to completion
    - If they start in the future: only count from start date to completion
    - Returns 0 if they start after completion
    """
    if work_start_date <= today:
        # Already working, count all months until completion
        return months_between_dates(today, completion_date)
    elif work_start_date < completion_date:
        # Will start working before completion
        return months_between_dates(work_start_date, completion_date)
    else:
        # Won't start working before completion
        return 0


# =============================================================================
# SIDEBAR - CONFIGURATION
# =============================================================================

def render_sidebar():
    """Render the configuration sidebar."""
    st.sidebar.title("🏠 BTO Calculator")
    st.sidebar.markdown("---")
    
    # =========================================================================
    # Section 1: Applicant Details
    # =========================================================================
    st.sidebar.header("👤 Applicant Details")
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        age_1 = st.number_input(
            "Applicant 1 Age",
            min_value=21,
            max_value=65,
            value=DEFAULTS["applicant_1_age"],
            help="Minimum age for HDB flat application is 21",
        )
    with col2:
        age_2 = st.number_input(
            "Applicant 2 Age",
            min_value=21,
            max_value=65,
            value=DEFAULTS["applicant_2_age"],
        )
    
    avg_age = (age_1 + age_2) / 2
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        income_1 = st.number_input(
            "Applicant 1 Gross Income",
            min_value=INCOME_MIN,
            max_value=INCOME_MAX,
            value=DEFAULTS["applicant_1_income"],
            step=INCOME_STEP,
            help="Monthly gross income before CPF deduction",
        )
    with col2:
        income_2 = st.number_input(
            "Applicant 2 Gross Income",
            min_value=INCOME_MIN,
            max_value=INCOME_MAX,
            value=DEFAULTS["applicant_2_income"],
            step=INCOME_STEP,
        )
    
    # Work start dates
    today = date.today()
    
    # Calculate default dates from DEFAULTS
    # If None, use today (currently working). If date object, use that date.
    default_work_start_1 = DEFAULTS["applicant_1_work_start_date"] if DEFAULTS["applicant_1_work_start_date"] is not None else today
    default_work_start_2 = DEFAULTS["applicant_2_work_start_date"] if DEFAULTS["applicant_2_work_start_date"] is not None else today
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        work_start_1 = st.date_input(
            "Applicant 1 Work Start",
            value=default_work_start_1,
            min_value=today - relativedelta(years=10),
            max_value=today + relativedelta(years=5),
            help="Date when applicant 1 starts/started working. Defaults to now (currently working).",
        )
    with col2:
        work_start_2 = st.date_input(
            "Applicant 2 Work Start",
            value=default_work_start_2,
            min_value=today - relativedelta(years=10),
            max_value=today + relativedelta(years=5),
            help="Date when applicant 2 starts/started working. Defaults to now (currently working).",
        )
    
    combined_income = income_1 + income_2
    st.sidebar.info(f"**Combined Gross Income:** {format_currency(combined_income)}")
    
    if combined_income > HDB_INCOME_CEILING:
        st.sidebar.warning(
            f"⚠️ Combined income exceeds HDB loan ceiling of {format_currency(HDB_INCOME_CEILING)}. "
            "You may need to consider a bank loan instead."
        )
    
    # =========================================================================
    # Section 2: Financial Commitments (Per Applicant)
    # =========================================================================
    st.sidebar.markdown("---")
    st.sidebar.header("💳 Financial Commitments")
    st.sidebar.caption("Monthly payments that reduce your loan eligibility")
    
    # Applicant 1 Commitments
    with st.sidebar.expander("👤 Applicant 1 Commitments"):
        credit_card_1 = st.number_input(
            "Credit Card Min. Payment",
            min_value=0,
            max_value=10000,
            value=DEFAULTS["applicant_1_credit_card"],
            step=50,
            key="cc1",
        )
        car_loan_1 = st.number_input(
            "Car Loan Payment",
            min_value=0,
            max_value=5000,
            value=DEFAULTS["applicant_1_car_loan"],
            step=50,
            key="car1",
        )
        other_loans_1 = st.number_input(
            "Other Loans",
            min_value=0,
            max_value=10000,
            value=DEFAULTS["applicant_1_other_loans"],
            step=50,
            key="other1",
        )
        total_1 = credit_card_1 + car_loan_1 + other_loans_1
        if total_1 > 0:
            st.caption(f"**Subtotal:** {format_currency(total_1)}/month")
    
    # Applicant 2 Commitments
    with st.sidebar.expander("👤 Applicant 2 Commitments"):
        credit_card_2 = st.number_input(
            "Credit Card Min. Payment",
            min_value=0,
            max_value=10000,
            value=DEFAULTS["applicant_2_credit_card"],
            step=50,
            key="cc2",
        )
        car_loan_2 = st.number_input(
            "Car Loan Payment",
            min_value=0,
            max_value=5000,
            value=DEFAULTS["applicant_2_car_loan"],
            step=50,
            key="car2",
        )
        other_loans_2 = st.number_input(
            "Other Loans",
            min_value=0,
            max_value=10000,
            value=DEFAULTS["applicant_2_other_loans"],
            step=50,
            key="other2",
        )
        total_2 = credit_card_2 + car_loan_2 + other_loans_2
        if total_2 > 0:
            st.caption(f"**Subtotal:** {format_currency(total_2)}/month")
    
    total_commitments = total_1 + total_2
    if total_commitments > 0:
        st.sidebar.warning(f"**Total Commitments:** {format_currency(total_commitments)}/month")
    
    # =========================================================================
    # Section 4: Current Savings (Per Applicant)
    # =========================================================================
    st.sidebar.markdown("---")
    st.sidebar.header("💰 Current Savings")
    
    # Applicant 1 Savings
    with st.sidebar.expander("👤 Applicant 1 Savings", expanded=True):
        cpf_oa_1 = st.number_input(
            "CPF OA Balance",
            min_value=0,
            max_value=1000000,
            value=DEFAULTS["applicant_1_cpf_oa"],
            step=1000,
            key="cpf1",
        )
        cash_1 = st.number_input(
            "Cash Savings",
            min_value=0,
            max_value=1000000,
            value=DEFAULTS["applicant_1_cash"],
            step=1000,
            key="cash1",
        )
        monthly_cash_savings_1 = st.number_input(
            "Monthly Cash Savings",
            min_value=0,
            max_value=20000,
            value=DEFAULTS["applicant_1_monthly_cash_savings"],
            step=100,
            key="monthly1",
        )
        # Calculate monthly CPF for applicant 1
        monthly_cpf_1 = calculate_monthly_cpf_oa(income_1, age_1)
        st.caption(f"**Monthly CPF OA:** {format_currency(monthly_cpf_1)}")
        
        # Show work status
        if work_start_1 > today:
            months_until = months_between_dates(today, work_start_1)
            st.caption(f"⏳ Starting work in {months_until} months")
    
    # Applicant 2 Savings
    with st.sidebar.expander("👤 Applicant 2 Savings", expanded=True):
        cpf_oa_2 = st.number_input(
            "CPF OA Balance",
            min_value=0,
            max_value=1000000,
            value=DEFAULTS["applicant_2_cpf_oa"],
            step=1000,
            key="cpf2",
        )
        cash_2 = st.number_input(
            "Cash Savings",
            min_value=0,
            max_value=1000000,
            value=DEFAULTS["applicant_2_cash"],
            step=1000,
            key="cash2",
        )
        monthly_cash_savings_2 = st.number_input(
            "Monthly Cash Savings",
            min_value=0,
            max_value=20000,
            value=DEFAULTS["applicant_2_monthly_cash_savings"],
            step=100,
            key="monthly2",
        )
        # Calculate monthly CPF for applicant 2
        monthly_cpf_2 = calculate_monthly_cpf_oa(income_2, age_2)
        st.caption(f"**Monthly CPF OA:** {format_currency(monthly_cpf_2)}")
        
        # Show work status
        if work_start_2 > today:
            months_until = months_between_dates(today, work_start_2)
            st.caption(f"⏳ Starting work in {months_until} months")
    
    # Combined totals
    current_cpf = cpf_oa_1 + cpf_oa_2
    current_cash = cash_1 + cash_2
    monthly_cash_savings = monthly_cash_savings_1 + monthly_cash_savings_2
    monthly_cpf = monthly_cpf_1 + monthly_cpf_2
    
    st.sidebar.info(
        f"**Combined Totals:**\n\n"
        f"CPF OA: {format_currency(current_cpf)}\n\n"
        f"Cash: {format_currency(current_cash)}\n\n"
        f"Monthly CPF: {format_currency(monthly_cpf)}\n\n"
        f"Monthly Cash: {format_currency(monthly_cash_savings)}"
    )
    
    # Savings health check
    combined_take_home = combined_income * 0.80  # After CPF
    if monthly_cash_savings > 0 and combined_take_home > 0:
        savings_check = check_savings_health(combined_income, monthly_cash_savings)
        
        if savings_check.status == "unsustainable":
            st.sidebar.error(savings_check.message)
        elif savings_check.status == "aggressive":
            st.sidebar.warning(savings_check.message)
        elif savings_check.status == "healthy":
            st.sidebar.success(savings_check.message)
        else:
            st.sidebar.info(savings_check.message)
    
    # =========================================================================
    # Section 5: Target Flat
    # =========================================================================
    st.sidebar.markdown("---")
    st.sidebar.header("🏢 Target Flat")
    
    # Initialize session state for target price sync
    if "target_price_slider" not in st.session_state:
        st.session_state.target_price_slider = DEFAULTS["target_flat_price"]
    if "target_price_input" not in st.session_state:
        st.session_state.target_price_input = DEFAULTS["target_flat_price"]
    
    # Sync function for target price
    def sync_target_price_from_slider():
        st.session_state.target_price_input = st.session_state.target_price_slider
    
    def sync_target_price_from_input():
        st.session_state.target_price_slider = st.session_state.target_price_input
    
    # Use columns for slider and number input
    col1, col2 = st.sidebar.columns([3, 1])
    with col1:
        st.slider(
            "Target Flat Price",
            min_value=FLAT_PRICE_MIN,
            max_value=FLAT_PRICE_MAX,
            step=FLAT_PRICE_STEP,
            format="$%d",
            key="target_price_slider",
            on_change=sync_target_price_from_slider,
        )
    with col2:
        st.number_input(
            "Exact Price",
            min_value=FLAT_PRICE_MIN,
            max_value=FLAT_PRICE_MAX,
            step=FLAT_PRICE_STEP,
            key="target_price_input",
            label_visibility="collapsed",
            on_change=sync_target_price_from_input,
        )
    
    target_price = st.session_state.target_price_slider
    
    # Completion date
    today = date.today()
    min_date = today + relativedelta(months=6)
    max_date = today + relativedelta(years=6)
    default_date = date(2028, 12, 31)  # Fixed default: 31 Dec 2028
    
    completion_date = st.sidebar.date_input(
        "Expected Completion Date",
        value=default_date,
        min_value=min_date,
        max_value=max_date,
        help="When do you expect the flat to be completed?",
    )
    
    months_to_completion = months_between_dates(today, completion_date)
    st.sidebar.info(f"**{months_to_completion} months** from now")
    
    # Return all config values
    return {
        "age_1": age_1,
        "age_2": age_2,
        "avg_age": avg_age,
        "income_1": income_1,
        "income_2": income_2,
        "combined_income": combined_income,
        "work_start_1": work_start_1,
        "work_start_2": work_start_2,
        # Per-applicant commitments
        "credit_card_1": credit_card_1,
        "car_loan_1": car_loan_1,
        "other_loans_1": other_loans_1,
        "credit_card_2": credit_card_2,
        "car_loan_2": car_loan_2,
        "other_loans_2": other_loans_2,
        "credit_card": credit_card_1 + credit_card_2,  # Combined for backward compatibility
        "car_loan": car_loan_1 + car_loan_2,  # Combined for backward compatibility
        "other_loans": other_loans_1 + other_loans_2,  # Combined for backward compatibility
        "total_commitments": total_commitments,
        # Per-applicant savings
        "cpf_oa_1": cpf_oa_1,
        "cash_1": cash_1,
        "monthly_cash_savings_1": monthly_cash_savings_1,
        "monthly_cash_1": monthly_cash_savings_1,  # Alias for convenience
        "monthly_cpf_1": monthly_cpf_1,
        "cpf_oa_2": cpf_oa_2,
        "cash_2": cash_2,
        "monthly_cash_savings_2": monthly_cash_savings_2,
        "monthly_cash_2": monthly_cash_savings_2,  # Alias for convenience
        "monthly_cpf_2": monthly_cpf_2,
        # Combined totals
        "current_cpf": current_cpf,
        "current_cash": current_cash,
        "monthly_cash_savings": monthly_cash_savings,
        "monthly_cpf": monthly_cpf,
        # Target flat
        "target_price": target_price,
        "completion_date": completion_date,
        "months_to_completion": months_to_completion,
    }


# =============================================================================
# MAIN CONTENT - TABS
# =============================================================================

def render_loan_eligibility_tab(config: dict):
    """Tab 1: Loan Eligibility Overview"""
    st.header("📊 Loan Eligibility")
    
    eligibility = calculate_loan_eligibility(
        gross_income=config["combined_income"],
        credit_card_payment=config["credit_card"],
        car_loan_payment=config["car_loan"],
        other_loan_payment=config["other_loans"],
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Maximum Monthly Installment",
            format_currency(eligibility.max_monthly_installment),
            help="30% of gross income minus existing commitments",
        )
        
    with col2:
        st.metric(
            "Maximum HDB Loan",
            format_currency(eligibility.max_loan_amount),
            help="Based on 25-year tenure at 2.6% interest",
        )
        
    with col3:
        st.metric(
            "Maximum Flat Price",
            format_currency(eligibility.max_flat_price),
            help="Based on 75% LTV (loan / 0.75)",
        )
    
    st.markdown("---")
    
    # Calculation details
    with st.expander("📝 Calculation Details", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Income & MSR**")
            st.write(f"- Gross Income: {format_currency(config['combined_income'])}")
            st.write(f"- MSR (30%): {format_currency(config['combined_income'] * MSR_LIMIT)}")
            st.write(f"- Existing Commitments: {format_currency(eligibility.total_commitments)}")
            st.write(f"- **Available for Mortgage:** {format_currency(eligibility.available_msr)}")
            
        with col2:
            st.markdown("**Loan Parameters**")
            st.write(f"- Interest Rate: {HDB_INTEREST_RATE * 100:.1f}% p.a.")
            st.write(f"- Maximum Tenure: {MAX_TENURE_YEARS} years")
            st.write(f"- Loan-to-Value: {LTV_LIMIT * 100:.0f}%")
            st.write(f"- Downpayment Required: {(1 - LTV_LIMIT) * 100:.0f}%")
    
    # MSR allocation chart
    if config["total_commitments"] > 0:
        st.subheader("MSR Allocation")
        fig = create_msr_allocation_chart(
            gross_income=config["combined_income"],
            existing_commitments=eligibility.total_commitments,
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Warnings
    if eligibility.exceeds_income_ceiling:
        st.error(
            f"⚠️ Your income exceeds the HDB loan ceiling of {format_currency(HDB_INCOME_CEILING)}. "
            "You may need to consider a bank loan, which typically has higher interest rates."
        )
    
    if eligibility.total_commitments > eligibility.available_msr * 0.5:
        st.warning(
            "⚠️ Your existing financial commitments are consuming more than 50% of your MSR. "
            "Consider paying off some debts to increase your loan eligibility."
        )
    
    return eligibility


def render_completion_tab(config: dict, eligibility):
    """Tab 2: Affordability at Completion Date"""
    st.header("📅 Affordability at Completion")
    
    months = config["months_to_completion"]
    today = date.today()
    
    # Calculate effective working months for each applicant
    working_months_1 = calculate_effective_working_months(
        config["work_start_1"], config["completion_date"], today
    )
    working_months_2 = calculate_effective_working_months(
        config["work_start_2"], config["completion_date"], today
    )
    
    # Project CPF balances separately for each applicant
    projected_cpf_1 = project_cpf_oa_with_interest(
        config["cpf_oa_1"],
        config["monthly_cpf_1"],
        working_months_1,
    )
    projected_cpf_2 = project_cpf_oa_with_interest(
        config["cpf_oa_2"],
        config["monthly_cpf_2"],
        working_months_2,
    )
    projected_cpf = projected_cpf_1 + projected_cpf_2
    
    # Project cash balances separately for each applicant
    projected_cash_1 = project_cash_balance(
        config["cash_1"],
        config["monthly_cash_1"],
        working_months_1,
    )
    projected_cash_2 = project_cash_balance(
        config["cash_2"],
        config["monthly_cash_2"],
        working_months_2,
    )
    projected_cash = projected_cash_1 + projected_cash_2
    
    # Calculate affordability
    affordability = calculate_affordability(
        target_flat_price=config["target_price"],
        loan_eligibility=eligibility,
        projected_cpf_oa=projected_cpf,
        projected_cash=projected_cash,
    )
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Target Flat Price",
            format_currency(config["target_price"]),
        )
    
    with col2:
        st.metric(
            "Total Upfront Required",
            format_currency(affordability.required_downpayment),
            help="25% downpayment + stamp duty + legal fees"
        )
    
    with col3:
        st.metric(
            "Projected Total Savings",
            format_currency(affordability.total_available),
            delta=format_currency(affordability.total_available - config["current_cpf"] - config["current_cash"]),
            help="CPF OA + Cash at completion date",
        )
    
    with col4:
        if affordability.can_afford:
            st.metric(
                "Status",
                "✅ Affordable",
                delta=f"Surplus: {format_currency(-affordability.downpayment_gap)}",
                delta_color="normal",
            )
        else:
            st.metric(
                "Status",
                "❌ Shortfall",
                delta=f"Gap: {format_currency(affordability.downpayment_gap)}",
                delta_color="inverse",
            )
    
    st.markdown("---")
    
    # Detailed breakdown
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💰 Your Resources at Completion")
        
        # Applicant 1 breakdown
        st.write(f"**Applicant 1:**")
        st.write(f"- Current CPF OA: {format_currency(config['cpf_oa_1'])}")
        if working_months_1 > 0:
            st.write(f"- + {working_months_1} months × {format_currency(config['monthly_cpf_1'])}/month")
            st.write(f"- + CPF interest (~2.5% p.a.)")
        elif config["work_start_1"] > today:
            st.write(f"- ⏳ Not working yet (starts in {months_between_dates(today, config['work_start_1'])} months)")
        st.write(f"- Projected CPF OA: {format_currency(projected_cpf_1)}")
        
        st.write(f"- Current Cash: {format_currency(config['cash_1'])}")
        if working_months_1 > 0:
            st.write(f"- + {working_months_1} months × {format_currency(config['monthly_cash_1'])}/month")
        st.write(f"- Projected Cash: {format_currency(projected_cash_1)}")
        
        st.markdown("---")
        
        # Applicant 2 breakdown
        st.write(f"**Applicant 2:**")
        st.write(f"- Current CPF OA: {format_currency(config['cpf_oa_2'])}")
        if working_months_2 > 0:
            st.write(f"- + {working_months_2} months × {format_currency(config['monthly_cpf_2'])}/month")
            st.write(f"- + CPF interest (~2.5% p.a.)")
        elif config["work_start_2"] > today:
            st.write(f"- ⏳ Not working yet (starts in {months_between_dates(today, config['work_start_2'])} months)")
        st.write(f"- Projected CPF OA: {format_currency(projected_cpf_2)}")
        
        st.write(f"- Current Cash: {format_currency(config['cash_2'])}")
        if working_months_2 > 0:
            st.write(f"- + {working_months_2} months × {format_currency(config['monthly_cash_2'])}/month")
        st.write(f"- Projected Cash: {format_currency(projected_cash_2)}")
        
        st.markdown("---")
        st.write(f"**Combined Total Available:** {format_currency(affordability.total_available)}")
    
    with col2:
        st.subheader("🏠 What You Need")
        st.write(f"**Flat Price Breakdown:**")
        st.write(f"- Flat Price: {format_currency(config['target_price'])}")
        st.write(f"- + Stamp Duty (BSD): {format_currency(affordability.stamp_duty)}")
        st.write(f"- + Legal Fees: {format_currency(affordability.legal_fees)}")
        st.write(f"- **Total Cost:** {format_currency(affordability.total_cost)}")
        st.markdown("---")
        st.write(f"**Financing:**")
        downpayment_on_flat = affordability.required_downpayment - affordability.stamp_duty - affordability.legal_fees
        st.write(f"- Downpayment (25%): {format_currency(downpayment_on_flat)}")
        st.write(f"- + Stamp Duty: {format_currency(affordability.stamp_duty)}")
        st.write(f"- + Legal Fees: {format_currency(affordability.legal_fees)}")
        st.write(f"- **= Upfront Required:** {format_currency(affordability.required_downpayment)}")
        st.write(f"- Loan Amount (75%): {format_currency(affordability.loan_amount)}")
        st.markdown("---")
        st.write(f"- Your Max Loan Eligibility: {format_currency(eligibility.max_loan_amount)}")
        loan_status = "✅ Within limit" if affordability.can_afford_loan else "❌ Exceeds limit"
        st.write(f"- Loan Status: {loan_status}")
        st.markdown("---")
        if affordability.can_afford:
            st.success(f"**You have a surplus of {format_currency(-affordability.downpayment_gap)}**")
        else:
            st.error(f"**You need {format_currency(affordability.downpayment_gap)} more**")
    
    # Affordability breakdown chart
    st.subheader("📊 Visual Breakdown")
    fig = create_affordability_breakdown_chart(
        flat_price=config["target_price"],
        loan_amount=affordability.loan_amount,
        required_downpayment=affordability.required_downpayment,
        projected_cpf=projected_cpf,
        projected_cash=projected_cash,
        max_loan_eligible=eligibility.max_loan_amount,
        stamp_duty=affordability.stamp_duty,
        legal_fees=affordability.legal_fees,
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # If not affordable, show what's needed
    if not affordability.can_afford:
        st.subheader("📈 What You Need to Afford This Flat")
        
        if not affordability.can_afford_downpayment:
            extra_needed = affordability.downpayment_gap
            extra_monthly = extra_needed / months if months > 0 else extra_needed
            st.warning(
                f"To afford the downpayment, you need to save an additional "
                f"**{format_currency(extra_monthly)}/month** for the next {months} months."
            )
        
        if not affordability.can_afford_loan:
            loan_gap = affordability.loan_amount - eligibility.max_loan_amount
            st.warning(
                f"The loan required ({format_currency(affordability.loan_amount)}) exceeds your eligibility "
                f"({format_currency(eligibility.max_loan_amount)}) by {format_currency(loan_gap)}. "
                "Consider a cheaper flat or increasing your income."
            )
    
    return affordability


def render_planner_tab(config: dict, eligibility):
    """Tab 3: Interactive Planner with charts"""
    st.header("📈 Interactive Planner")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("⚙️ Adjust Timeline")
        max_months = st.slider(
            "Planning Horizon (months)",
            min_value=12,
            max_value=72,
            value=36,
            step=6,
        )
    
    with col1:
        # Savings projection chart
        st.subheader("💰 Savings Growth Over Time")
        
        # Calculate total upfront required (25% + stamp duty + legal fees for purchase & mortgage)
        loan_amt = calculate_loan_amount(config["target_price"])
        stamp_duty = calculate_stamp_duty(config["target_price"])
        legal_fees = calculate_hdb_legal_fees(config["target_price"]) + calculate_hdb_legal_fees(loan_amt)
        downpayment_on_flat = calculate_required_downpayment(config["target_price"])
        required_dp = downpayment_on_flat + stamp_duty + legal_fees
        
        fig = create_savings_projection_chart(
            current_cpf_oa=config["current_cpf"],
            current_cash=config["current_cash"],
            monthly_cpf_contribution=config["monthly_cpf"],
            monthly_cash_savings=config["monthly_cash_savings"],
            required_downpayment=required_dp,
            completion_months=config["months_to_completion"],
            max_months=max_months,
            cpf_oa_1=config["cpf_oa_1"],
            cpf_oa_2=config["cpf_oa_2"],
            cash_1=config["cash_1"],
            cash_2=config["cash_2"],
            monthly_cpf_1=config["monthly_cpf_1"],
            monthly_cpf_2=config["monthly_cpf_2"],
            monthly_cash_1=config["monthly_cash_1"],
            monthly_cash_2=config["monthly_cash_2"],
            work_start_1=config["work_start_1"],
            work_start_2=config["work_start_2"],
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Max affordable flat over time
    st.subheader("🏠 Maximum Affordable Flat Over Time")
    st.caption(
        "As your savings grow, the maximum flat you can afford increases "
        "(until you hit your loan eligibility limit)"
    )
    
    fig2 = create_max_affordable_over_time_chart(
        current_cpf=config["current_cpf"],
        current_cash=config["current_cash"],
        monthly_cpf=config["monthly_cpf"],
        monthly_cash=config["monthly_cash_savings"],
        max_loan=eligibility.max_loan_amount,
        max_months=max_months,
        cpf_oa_1=config["cpf_oa_1"],
        cpf_oa_2=config["cpf_oa_2"],
        cash_1=config["cash_1"],
        cash_2=config["cash_2"],
        monthly_cpf_1=config["monthly_cpf_1"],
        monthly_cpf_2=config["monthly_cpf_2"],
        monthly_cash_1=config["monthly_cash_1"],
        monthly_cash_2=config["monthly_cash_2"],
        work_start_1=config["work_start_1"],
        work_start_2=config["work_start_2"],
    )
    st.plotly_chart(fig2, use_container_width=True)
    
    # Find when target flat becomes affordable
    today = date.today()
    for m in range(1, max_months + 1):
        future_date = today + relativedelta(months=m)
        
        # Calculate effective working months for each applicant up to this point
        working_m_1 = calculate_effective_working_months(config["work_start_1"], future_date, today)
        working_m_2 = calculate_effective_working_months(config["work_start_2"], future_date, today)
        
        # Project balances for each applicant
        cpf_1 = project_cpf_oa_with_interest(config["cpf_oa_1"], config["monthly_cpf_1"], working_m_1)
        cpf_2 = project_cpf_oa_with_interest(config["cpf_oa_2"], config["monthly_cpf_2"], working_m_2)
        cpf = cpf_1 + cpf_2
        
        cash_1 = project_cash_balance(config["cash_1"], config["monthly_cash_1"], working_m_1)
        cash_2 = project_cash_balance(config["cash_2"], config["monthly_cash_2"], working_m_2)
        cash = cash_1 + cash_2
        
        total = cpf + cash
        
        # Calculate total upfront required (25% + stamp duty + legal fees for purchase & mortgage)
        loan_needed = calculate_loan_amount(config["target_price"])
        downpayment_on_flat = calculate_required_downpayment(config["target_price"])
        stamp_duty_amt = calculate_stamp_duty(config["target_price"])
        legal_fees_total = calculate_hdb_legal_fees(config["target_price"]) + calculate_hdb_legal_fees(loan_needed)
        required = downpayment_on_flat + stamp_duty_amt + legal_fees_total
        
        if total >= required and loan_needed <= eligibility.max_loan_amount:
            affordable_date = future_date
            st.success(
                f"🎉 You can afford the {format_currency(config['target_price'])} flat in "
                f"**{m} months** (around {affordable_date.strftime('%B %Y')})"
            )
            break
    else:
        if calculate_loan_amount(config["target_price"]) > eligibility.max_loan_amount:
            st.error(
                f"❌ The loan required for this flat ({format_currency(calculate_loan_amount(config['target_price']))}) "
                f"exceeds your maximum eligibility ({format_currency(eligibility.max_loan_amount)}). "
                "Consider a cheaper flat."
            )
        else:
            st.warning(
                f"⚠️ At current savings rate, you won't have enough for downpayment within {max_months} months. "
                "Consider increasing your monthly savings."
            )


def render_whatif_tab(config: dict):
    """Tab 4: What-If Analysis"""
    st.header("🔮 What-If Analysis")
    st.caption("See how changes to your finances affect your eligibility")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📉 Reduce Commitments")
        
        remove_car = st.checkbox(
            f"Pay off car loan ({format_currency(config['car_loan'])}/month)",
            disabled=config["car_loan"] == 0,
        )
        remove_cc = st.checkbox(
            f"Pay off credit card ({format_currency(config['credit_card'])}/month)",
            disabled=config["credit_card"] == 0,
        )
        remove_other = st.checkbox(
            f"Pay off other loans ({format_currency(config['other_loans'])}/month)",
            disabled=config["other_loans"] == 0,
        )
    
    with col2:
        st.subheader("📈 Adjust Income")
        
        st.caption(f"Current: Applicant 1 = {format_currency(config['income_1'])}, Applicant 2 = {format_currency(config['income_2'])}")
        
        # Initialize session state for what-if incomes
        if "whatif_income_1_slider" not in st.session_state:
            st.session_state.whatif_income_1_slider = config['income_1']
        if "whatif_income_1_input" not in st.session_state:
            st.session_state.whatif_income_1_input = config['income_1']
        if "whatif_income_2_slider" not in st.session_state:
            st.session_state.whatif_income_2_slider = config['income_2']
        if "whatif_income_2_input" not in st.session_state:
            st.session_state.whatif_income_2_input = config['income_2']
        
        # Sync functions
        def sync_income_1_from_slider():
            st.session_state.whatif_income_1_input = st.session_state.whatif_income_1_slider
        
        def sync_income_1_from_input():
            st.session_state.whatif_income_1_slider = st.session_state.whatif_income_1_input
        
        def sync_income_2_from_slider():
            st.session_state.whatif_income_2_input = st.session_state.whatif_income_2_slider
        
        def sync_income_2_from_input():
            st.session_state.whatif_income_2_slider = st.session_state.whatif_income_2_input
        
        # Applicant 1 income adjustment
        col_slider1, col_input1 = st.columns([3, 1])
        with col_slider1:
            st.slider(
                "Applicant 1 Gross Income",
                min_value=INCOME_MIN,
                max_value=INCOME_MAX,
                step=INCOME_STEP,
                key="whatif_income_1_slider",
                on_change=sync_income_1_from_slider,
            )
        with col_input1:
            st.number_input(
                "A1",
                min_value=INCOME_MIN,
                max_value=INCOME_MAX,
                step=INCOME_STEP,
                key="whatif_income_1_input",
                label_visibility="collapsed",
                on_change=sync_income_1_from_input,
            )
        new_income_1 = st.session_state.whatif_income_1_slider
        
        # Applicant 2 income adjustment
        col_slider2, col_input2 = st.columns([3, 1])
        with col_slider2:
            st.slider(
                "Applicant 2 Gross Income",
                min_value=INCOME_MIN,
                max_value=INCOME_MAX,
                step=INCOME_STEP,
                key="whatif_income_2_slider",
                on_change=sync_income_2_from_slider,
            )
        with col_input2:
            st.number_input(
                "A2",
                min_value=INCOME_MIN,
                max_value=INCOME_MAX,
                step=INCOME_STEP,
                key="whatif_income_2_input",
                label_visibility="collapsed",
                on_change=sync_income_2_from_input,
            )
        new_income_2 = st.session_state.whatif_income_2_slider
        
        new_combined_income = new_income_1 + new_income_2
        income_change = new_combined_income - config["combined_income"]
        
        if income_change != 0:
            st.caption(f"New combined: {format_currency(new_combined_income)} ({'+' if income_change > 0 else ''}{format_currency(income_change)})")
    
    # Calculate new eligibility
    new_commitments = (
        (0 if remove_car else config["car_loan"]) +
        (0 if remove_cc else config["credit_card"]) +
        (0 if remove_other else config["other_loans"])
    )
    
    new_income = new_combined_income
    
    current_eligibility = calculate_loan_eligibility(
        gross_income=config["combined_income"],
        credit_card_payment=config["credit_card"],
        car_loan_payment=config["car_loan"],
        other_loan_payment=config["other_loans"],
    )
    
    new_eligibility = calculate_loan_eligibility(
        gross_income=new_income,
        credit_card_payment=0 if remove_cc else config["credit_card"],
        car_loan_payment=0 if remove_car else config["car_loan"],
        other_loan_payment=0 if remove_other else config["other_loans"],
    )
    
    # Show comparison
    st.markdown("---")
    st.subheader("📊 Impact on Eligibility")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        delta_msr = new_eligibility.max_monthly_installment - current_eligibility.max_monthly_installment
        st.metric(
            "Max Monthly Installment",
            format_currency(new_eligibility.max_monthly_installment),
            delta=f"+{format_currency(delta_msr)}" if delta_msr > 0 else format_currency(delta_msr),
        )
    
    with col2:
        delta_loan = new_eligibility.max_loan_amount - current_eligibility.max_loan_amount
        st.metric(
            "Max Loan Amount",
            format_currency(new_eligibility.max_loan_amount),
            delta=f"+{format_currency(delta_loan)}" if delta_loan > 0 else format_currency(delta_loan),
        )
    
    with col3:
        delta_flat = new_eligibility.max_flat_price - current_eligibility.max_flat_price
        st.metric(
            "Max Flat Price",
            format_currency(new_eligibility.max_flat_price),
            delta=f"+{format_currency(delta_flat)}" if delta_flat > 0 else format_currency(delta_flat),
        )
    
    if delta_flat > 0:
        st.success(
            f"💡 By making these changes, you could afford a flat that's "
            f"**{format_currency(delta_flat)} more expensive**!"
        )
    elif delta_flat < 0:
        st.warning(
            f"⚠️ These changes reduce your affordability by "
            f"**{format_currency(abs(delta_flat))}**."
        )


def render_tenure_optimizer_tab(config: dict, eligibility):
    """Tab 5: Tenure Optimization"""
    st.header("⚖️ Tenure Optimizer")
    st.caption("Find the optimal balance between affordable payments and interest savings")
    
    # Calculate loan for target flat
    loan_amount = calculate_loan_amount(config["target_price"])
    
    if loan_amount > eligibility.max_loan_amount:
        st.error(
            f"⚠️ The loan required ({format_currency(loan_amount)}) exceeds your eligibility "
            f"({format_currency(eligibility.max_loan_amount)}). Adjust your target flat price first."
        )
        loan_amount = eligibility.max_loan_amount
    
    st.info(f"Analyzing tenure options for a **{format_currency(loan_amount)}** loan")
    
    # Tenure slider
    selected_tenure = st.slider(
        "Select Loan Tenure (Years)",
        min_value=5,
        max_value=25,
        value=25,
    )
    
    # Calculate for selected tenure
    monthly_payment = calculate_monthly_payment(loan_amount, HDB_INTEREST_RATE, selected_tenure)
    total_interest = calculate_total_interest(loan_amount, HDB_INTEREST_RATE, selected_tenure)
    interest_at_25 = calculate_total_interest(loan_amount, HDB_INTEREST_RATE, 25)
    interest_saved = interest_at_25 - total_interest
    
    is_affordable = monthly_payment <= eligibility.max_monthly_installment
    
    # Display metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Monthly Payment",
            format_currency(monthly_payment),
            delta="✅ Affordable" if is_affordable else "❌ Exceeds MSR",
            delta_color="normal" if is_affordable else "inverse",
        )
    
    with col2:
        st.metric(
            "Total Interest",
            format_currency(total_interest),
        )
    
    with col3:
        st.metric(
            "Total Cost",
            format_currency(loan_amount + total_interest),
        )
    
    with col4:
        st.metric(
            "Interest Saved vs 25yr",
            format_currency(interest_saved),
            delta=f"{interest_saved / interest_at_25 * 100:.0f}% saved" if interest_at_25 > 0 else None,
        )
    
    st.markdown("---")
    
    # Tenure comparison chart
    st.subheader("📊 Trade-off: Monthly Payment vs Total Interest")
    
    fig = create_tenure_comparison_chart(
        loan_amount=loan_amount,
        max_monthly_payment=eligibility.max_monthly_installment,
        interest_rate=HDB_INTEREST_RATE,
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Tenure comparison table
    st.subheader("📋 Tenure Comparison")
    
    table_data = create_tenure_table_data(
        loan_amount=loan_amount,
        max_monthly_payment=eligibility.max_monthly_installment,
        key_tenures=[10, 15, 20, 25],
    )
    
    df = pd.DataFrame(table_data)
    st.dataframe(df, hide_index=True, use_container_width=True)
    
    # Find optimal tenure
    st.markdown("---")
    st.subheader("🎯 Optimal Tenure Recommendation")
    
    comfort_buffer = st.slider(
        "Comfort Buffer (below MSR limit)",
        min_value=0,
        max_value=1000,
        value=200,
        step=50,
        help="Leave some room below your MSR limit for financial flexibility",
    )
    
    optimal = find_optimal_tenure(
        loan_amount=loan_amount,
        max_monthly_payment=eligibility.max_monthly_installment,
        comfort_buffer=comfort_buffer,
    )
    
    if optimal:
        st.success(
            f"**Recommended Tenure: {optimal.tenure_years} years**\n\n"
            f"- Monthly Payment: {format_currency(optimal.monthly_payment)}\n"
            f"- MSR Buffer: {format_currency(optimal.msr_buffer)}\n"
            f"- Total Interest: {format_currency(optimal.total_interest)}\n"
            f"- Interest Saved vs 25 years: {format_currency(optimal.interest_saved_vs_max)}"
        )
    else:
        st.error(
            "❌ Cannot find an affordable tenure with your current eligibility. "
            "Consider reducing the flat price or increasing your income."
        )


# =============================================================================
# MAIN APP
# =============================================================================

def main():
    """Main application entry point."""
    
    # Render sidebar and get config
    config = render_sidebar()
    
    # Calculate initial eligibility
    eligibility = calculate_loan_eligibility(
        gross_income=config["combined_income"],
        credit_card_payment=config["credit_card"],
        car_loan_payment=config["car_loan"],
        other_loan_payment=config["other_loans"],
    )
    
    # Main content area with tabs
    st.title("🏠 Singapore BTO Flat Affordability Calculator")
    st.caption(
        "Plan your HDB BTO flat purchase with confidence. "
        "Calculate loan eligibility, project CPF savings, and optimize your purchase strategy."
    )
    
    tabs = st.tabs([
        "📊 Loan Eligibility",
        "📅 By Completion Date",
        "📈 Interactive Planner",
        "🔮 What-If Analysis",
        "⚖️ Tenure Optimizer",
    ])
    
    with tabs[0]:
        eligibility = render_loan_eligibility_tab(config)
    
    with tabs[1]:
        render_completion_tab(config, eligibility)
    
    with tabs[2]:
        render_planner_tab(config, eligibility)
    
    with tabs[3]:
        render_whatif_tab(config)
    
    with tabs[4]:
        render_tenure_optimizer_tab(config, eligibility)
    
    # Footer
    st.markdown("---")
    st.caption(
        "**Disclaimer:** This calculator provides estimates only and should not be considered financial advice. "
        "Actual HDB loan eligibility depends on various factors assessed by HDB at the time of application. "
        "Please consult HDB or a financial advisor for official assessments."
    )
    st.caption(
        f"Interest Rate: {HDB_INTEREST_RATE * 100:.1f}% p.a. | "
        f"LTV: {LTV_LIMIT * 100:.0f}% | "
        f"MSR: {MSR_LIMIT * 100:.0f}% | "
        f"Max Tenure: {MAX_TENURE_YEARS} years"
    )


if __name__ == "__main__":
    main()
