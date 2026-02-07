"""
Singapore HDB BTO Flat Affordability Calculator - Charts

Plotly chart generators for visualizing affordability, projections,
and tenure analysis.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from calculations import (
    TenureAnalysis,
    calculate_monthly_payment,
    calculate_total_interest,
    project_cpf_oa_balance,
    project_cash_balance,
    format_currency,
)
from constants import HDB_INTEREST_RATE, MAX_TENURE_YEARS


# =============================================================================
# COLOR SCHEME
# =============================================================================

COLORS = {
    "primary": "#1f77b4",      # Blue
    "secondary": "#ff7f0e",    # Orange
    "success": "#2ca02c",      # Green
    "danger": "#d62728",       # Red
    "warning": "#ffbb33",      # Yellow
    "info": "#17becf",         # Cyan
    "cpf": "#9467bd",          # Purple (for CPF)
    "cash": "#8c564b",         # Brown (for Cash)
    "loan": "#1f77b4",         # Blue (for Loan)
    "downpayment": "#2ca02c",  # Green (for Downpayment)
    "affordable": "rgba(44, 160, 44, 0.2)",   # Light green
    "unaffordable": "rgba(214, 39, 40, 0.2)", # Light red
}


# =============================================================================
# SAVINGS PROJECTION CHART
# =============================================================================

def create_savings_projection_chart(
    current_cpf_oa: float,
    current_cash: float,
    monthly_cpf_contribution: float,
    monthly_cash_savings: float,
    required_downpayment: float,
    completion_months: int,
    max_months: int = 60,
    cpf_oa_1: float = None,
    cpf_oa_2: float = None,
    cash_1: float = None,
    cash_2: float = None,
    monthly_cpf_1: float = None,
    monthly_cpf_2: float = None,
    monthly_cash_1: float = None,
    monthly_cash_2: float = None,
    work_start_1 = None,
    work_start_2 = None,
) -> go.Figure:
    """
    Create a line chart showing projected savings over time.
    
    Shows:
    - CPF OA projection
    - Cash savings projection
    - Combined total
    - Required downpayment line
    - Completion date marker
    
    Supports per-applicant tracking with work start dates.
    """
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    # If per-applicant data provided, use it; otherwise use combined values
    use_per_applicant = all(x is not None for x in [cpf_oa_1, cpf_oa_2, monthly_cpf_1, monthly_cpf_2])
    
    months = list(range(0, max_months + 1))
    today = date.today() if work_start_1 is not None else None
    
    cpf_projection = []
    cash_projection = []
    
    for m in months:
        if use_per_applicant and today is not None:
            # Calculate per-applicant with work start dates
            future_date = today + relativedelta(months=m)
            
            # Helper to calculate effective months
            def calc_working_months(work_start, target_date):
                if work_start <= today:
                    return (target_date.year - today.year) * 12 + target_date.month - today.month
                elif work_start < target_date:
                    return (target_date.year - work_start.year) * 12 + target_date.month - work_start.month
                else:
                    return 0
            
            working_m_1 = calc_working_months(work_start_1, future_date) if work_start_1 else m
            working_m_2 = calc_working_months(work_start_2, future_date) if work_start_2 else m
            
            cpf_1 = project_cpf_oa_balance(cpf_oa_1, monthly_cpf_1, working_m_1)
            cpf_2 = project_cpf_oa_balance(cpf_oa_2, monthly_cpf_2, working_m_2)
            cpf = cpf_1 + cpf_2
            
            cash_proj_1 = project_cash_balance(cash_1, monthly_cash_1, working_m_1)
            cash_proj_2 = project_cash_balance(cash_2, monthly_cash_2, working_m_2)
            cash = cash_proj_1 + cash_proj_2
        else:
            # Use combined values (backward compatibility)
            cpf = project_cpf_oa_balance(current_cpf_oa, monthly_cpf_contribution, m)
            cash = project_cash_balance(current_cash, monthly_cash_savings, m)
        
        cpf_projection.append(cpf)
        cash_projection.append(cash)
    
    total_projection = [cpf + cash for cpf, cash in zip(cpf_projection, cash_projection)]
    
    fig = go.Figure()
    
    # Add traces
    fig.add_trace(go.Scatter(
        x=months,
        y=cpf_projection,
        name="CPF OA",
        line=dict(color=COLORS["cpf"], width=2),
        hovertemplate="Month %{x}<br>CPF OA: $%{y:,.0f}<extra></extra>",
    ))
    
    fig.add_trace(go.Scatter(
        x=months,
        y=cash_projection,
        name="Cash Savings",
        line=dict(color=COLORS["cash"], width=2),
        hovertemplate="Month %{x}<br>Cash: $%{y:,.0f}<extra></extra>",
    ))
    
    fig.add_trace(go.Scatter(
        x=months,
        y=total_projection,
        name="Total Available",
        line=dict(color=COLORS["primary"], width=3),
        hovertemplate="Month %{x}<br>Total: $%{y:,.0f}<extra></extra>",
    ))
    
    # Required downpayment line
    fig.add_hline(
        y=required_downpayment,
        line=dict(color=COLORS["danger"], width=2, dash="dash"),
        annotation_text=f"Required: {format_currency(required_downpayment)}",
        annotation_position="right",
    )
    
    # Completion date vertical line
    if completion_months <= max_months:
        total_at_completion = total_projection[completion_months] if completion_months < len(total_projection) else total_projection[-1]
        fig.add_vline(
            x=completion_months,
            line=dict(color=COLORS["secondary"], width=2, dash="dot"),
            annotation_text=f"Completion\n({completion_months} months)",
            annotation_position="top",
        )
        
        # Add marker at completion
        fig.add_trace(go.Scatter(
            x=[completion_months],
            y=[total_at_completion],
            mode="markers",
            name="At Completion",
            marker=dict(size=12, color=COLORS["secondary"], symbol="star"),
            hovertemplate=f"At Completion<br>Total: ${total_at_completion:,.0f}<extra></extra>",
        ))
    
    # Find intersection point (when total meets downpayment)
    for i, total in enumerate(total_projection):
        if total >= required_downpayment:
            fig.add_trace(go.Scatter(
                x=[i],
                y=[required_downpayment],
                mode="markers",
                name="Affordability Point",
                marker=dict(size=15, color=COLORS["success"], symbol="diamond"),
                hovertemplate=f"Affordable at month {i}<br>Amount: ${total:,.0f}<extra></extra>",
            ))
            break
    
    fig.update_layout(
        title="Savings Projection Over Time",
        xaxis_title="Months from Now",
        yaxis_title="Amount ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400,
    )
    
    fig.update_yaxes(tickformat="$,.0f")
    
    return fig


# =============================================================================
# TENURE COMPARISON CHART
# =============================================================================

def create_tenure_comparison_chart(
    loan_amount: float,
    max_monthly_payment: float,
    interest_rate: float = HDB_INTEREST_RATE
) -> go.Figure:
    """
    Create a dual-axis chart showing monthly payment vs total interest
    for different loan tenures.
    
    Highlights the affordable zone and optimal tenure.
    """
    tenures = list(range(5, MAX_TENURE_YEARS + 1))
    
    monthly_payments = [calculate_monthly_payment(loan_amount, interest_rate, t) for t in tenures]
    total_interests = [calculate_total_interest(loan_amount, interest_rate, t) for t in tenures]
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Monthly payment (left axis)
    fig.add_trace(
        go.Scatter(
            x=tenures,
            y=monthly_payments,
            name="Monthly Payment",
            line=dict(color=COLORS["primary"], width=3),
            hovertemplate="Tenure: %{x} years<br>Monthly: $%{y:,.0f}<extra></extra>",
        ),
        secondary_y=False,
    )
    
    # Total interest (right axis)
    fig.add_trace(
        go.Scatter(
            x=tenures,
            y=total_interests,
            name="Total Interest",
            line=dict(color=COLORS["secondary"], width=3),
            hovertemplate="Tenure: %{x} years<br>Interest: $%{y:,.0f}<extra></extra>",
        ),
        secondary_y=True,
    )
    
    # MSR limit line
    fig.add_hline(
        y=max_monthly_payment,
        line=dict(color=COLORS["danger"], width=2, dash="dash"),
        annotation_text=f"MSR Limit: {format_currency(max_monthly_payment)}",
        annotation_position="right",
        secondary_y=False,
    )
    
    # Find and highlight affordable zone
    affordable_tenures = [t for t, p in zip(tenures, monthly_payments) if p <= max_monthly_payment]
    if affordable_tenures:
        min_affordable = min(affordable_tenures)
        max_affordable = max(affordable_tenures)
        
        # Shade affordable region
        fig.add_vrect(
            x0=min_affordable - 0.5,
            x1=max_affordable + 0.5,
            fillcolor=COLORS["affordable"],
            layer="below",
            line_width=0,
            annotation_text="Affordable Zone",
            annotation_position="top left",
        )
        
        # Mark optimal (shortest affordable)
        optimal_payment = monthly_payments[tenures.index(min_affordable)]
        optimal_interest = total_interests[tenures.index(min_affordable)]
        
        fig.add_trace(
            go.Scatter(
                x=[min_affordable],
                y=[optimal_payment],
                mode="markers+text",
                name="Optimal Tenure",
                marker=dict(size=15, color=COLORS["success"], symbol="star"),
                text=[f"Optimal: {min_affordable} yrs"],
                textposition="top center",
                hovertemplate=f"Optimal: {min_affordable} years<br>Monthly: ${optimal_payment:,.0f}<br>Total Interest: ${optimal_interest:,.0f}<extra></extra>",
            ),
            secondary_y=False,
        )
    
    fig.update_layout(
        title="Tenure Trade-off: Monthly Payment vs Total Interest",
        xaxis_title="Loan Tenure (Years)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=450,
    )
    
    fig.update_yaxes(title_text="Monthly Payment ($)", tickformat="$,.0f", secondary_y=False)
    fig.update_yaxes(title_text="Total Interest ($)", tickformat="$,.0f", secondary_y=True)
    
    return fig


# =============================================================================
# AFFORDABILITY BREAKDOWN CHART
# =============================================================================

def create_affordability_breakdown_chart(
    flat_price: float,
    loan_amount: float,
    required_downpayment: float,
    projected_cpf: float,
    projected_cash: float,
    max_loan_eligible: float,
    stamp_duty: float = 0,
    legal_fees: float = 0
) -> go.Figure:
    """
    Create a horizontal bar chart showing affordability breakdown.
    
    Shows:
    - What's needed (downpayment, stamp duty, legal fees, loan)
    - What you have (CPF, Cash, Loan eligibility)
    """
    fig = go.Figure()
    
    # Calculate downpayment on flat (25%)
    downpayment_on_flat = required_downpayment - stamp_duty - legal_fees if stamp_duty > 0 else required_downpayment
    
    # What's needed - broken down
    if stamp_duty > 0 and legal_fees > 0:
        # Show detailed breakdown
        fig.add_trace(go.Bar(
            y=["Flat Cost Breakdown"],
            x=[downpayment_on_flat],
            name=f"Downpayment (25%): {format_currency(downpayment_on_flat)}",
            orientation="h",
            marker_color=COLORS["downpayment"],
            text=[format_currency(downpayment_on_flat)],
            textposition="inside",
        ))
        
        fig.add_trace(go.Bar(
            y=["Flat Cost Breakdown"],
            x=[stamp_duty],
            name=f"Stamp Duty: {format_currency(stamp_duty)}",
            orientation="h",
            marker_color=COLORS["warning"],
            text=[format_currency(stamp_duty)],
            textposition="inside",
        ))
        
        fig.add_trace(go.Bar(
            y=["Flat Cost Breakdown"],
            x=[legal_fees],
            name=f"Legal Fees: {format_currency(legal_fees)}",
            orientation="h",
            marker_color=COLORS["info"],
            text=[format_currency(legal_fees)],
            textposition="inside",
        ))
    else:
        # Simplified view
        fig.add_trace(go.Bar(
            y=["Flat Cost Breakdown"],
            x=[required_downpayment],
            name=f"Upfront Required: {format_currency(required_downpayment)}",
            orientation="h",
            marker_color=COLORS["downpayment"],
            text=[format_currency(required_downpayment)],
            textposition="inside",
        ))
    
    fig.add_trace(go.Bar(
        y=["Flat Cost Breakdown"],
        x=[loan_amount],
        name=f"Loan (75%): {format_currency(loan_amount)}",
        orientation="h",
        marker_color=COLORS["loan"],
        text=[format_currency(loan_amount)],
        textposition="inside",
    ))
    
    # What you have
    total_available = projected_cpf + projected_cash
    fig.add_trace(go.Bar(
        y=["Your Resources"],
        x=[projected_cpf],
        name=f"CPF OA: {format_currency(projected_cpf)}",
        orientation="h",
        marker_color=COLORS["cpf"],
        text=[format_currency(projected_cpf)],
        textposition="inside",
    ))
    
    fig.add_trace(go.Bar(
        y=["Your Resources"],
        x=[projected_cash],
        name=f"Cash: {format_currency(projected_cash)}",
        orientation="h",
        marker_color=COLORS["cash"],
        text=[format_currency(projected_cash)],
        textposition="inside",
    ))
    
    # Loan eligibility
    fig.add_trace(go.Bar(
        y=["Loan Eligibility"],
        x=[max_loan_eligible],
        name=f"Max Loan: {format_currency(max_loan_eligible)}",
        orientation="h",
        marker_color=COLORS["info"],
        text=[format_currency(max_loan_eligible)],
        textposition="inside",
    ))
    
    fig.update_layout(
        title="Affordability Breakdown",
        barmode="stack",
        xaxis_title="Amount ($)",
        height=300,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        showlegend=True,
    )
    
    fig.update_xaxes(tickformat="$,.0f")
    
    return fig


# =============================================================================
# MSR ALLOCATION PIE CHART
# =============================================================================

def create_msr_allocation_chart(
    gross_income: float,
    existing_commitments: float,
    proposed_mortgage: float = 0
) -> go.Figure:
    """
    Create a pie chart showing how MSR is allocated.
    """
    total_msr = gross_income * 0.30
    remaining = max(0, total_msr - existing_commitments - proposed_mortgage)
    
    values = []
    labels = []
    colors = []
    
    if existing_commitments > 0:
        values.append(existing_commitments)
        labels.append(f"Existing Commitments<br>{format_currency(existing_commitments)}")
        colors.append(COLORS["warning"])
    
    if proposed_mortgage > 0:
        values.append(proposed_mortgage)
        labels.append(f"Proposed Mortgage<br>{format_currency(proposed_mortgage)}")
        colors.append(COLORS["primary"])
    
    if remaining > 0:
        values.append(remaining)
        labels.append(f"Available<br>{format_currency(remaining)}")
        colors.append(COLORS["success"])
    
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        marker_colors=colors,
        hole=0.4,
        textinfo="percent",
        textposition="outside",
        hovertemplate="%{label}<br>%{percent}<extra></extra>",
    )])
    
    fig.update_layout(
        title=f"MSR Allocation (30% of {format_currency(gross_income)} = {format_currency(total_msr)})",
        height=350,
        showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.1),
    )
    
    return fig


# =============================================================================
# MAX AFFORDABLE FLAT OVER TIME CHART
# =============================================================================

def create_max_affordable_over_time_chart(
    current_cpf: float,
    current_cash: float,
    monthly_cpf: float,
    monthly_cash: float,
    max_loan: float,
    max_months: int = 60,
    cpf_oa_1: float = None,
    cpf_oa_2: float = None,
    cash_1: float = None,
    cash_2: float = None,
    monthly_cpf_1: float = None,
    monthly_cpf_2: float = None,
    monthly_cash_1: float = None,
    monthly_cash_2: float = None,
    work_start_1 = None,
    work_start_2 = None,
) -> go.Figure:
    """
    Create a chart showing maximum affordable flat price over time.
    
    As savings grow, the maximum flat you can afford increases
    (up to the loan-limited ceiling).
    
    Supports per-applicant tracking with work start dates.
    """
    from constants import LTV_LIMIT
    from datetime import date
    from dateutil.relativedelta import relativedelta
    
    # If per-applicant data provided, use it; otherwise use combined values
    use_per_applicant = all(x is not None for x in [cpf_oa_1, cpf_oa_2, monthly_cpf_1, monthly_cpf_2])
    
    months = list(range(0, max_months + 1))
    today = date.today() if work_start_1 is not None else None
    
    max_affordable_prices = []
    for m in months:
        if use_per_applicant and today is not None:
            # Calculate per-applicant with work start dates
            future_date = today + relativedelta(months=m)
            
            # Helper to calculate effective months
            def calc_working_months(work_start, target_date):
                if work_start <= today:
                    return (target_date.year - today.year) * 12 + target_date.month - today.month
                elif work_start < target_date:
                    return (target_date.year - work_start.year) * 12 + target_date.month - work_start.month
                else:
                    return 0
            
            working_m_1 = calc_working_months(work_start_1, future_date) if work_start_1 else m
            working_m_2 = calc_working_months(work_start_2, future_date) if work_start_2 else m
            
            cpf_proj_1 = project_cpf_oa_balance(cpf_oa_1, monthly_cpf_1, working_m_1)
            cpf_proj_2 = project_cpf_oa_balance(cpf_oa_2, monthly_cpf_2, working_m_2)
            cpf = cpf_proj_1 + cpf_proj_2
            
            cash_proj_1 = project_cash_balance(cash_1, monthly_cash_1, working_m_1)
            cash_proj_2 = project_cash_balance(cash_2, monthly_cash_2, working_m_2)
            cash = cash_proj_1 + cash_proj_2
        else:
            # Use combined values (backward compatibility)
            cpf = project_cpf_oa_balance(current_cpf, monthly_cpf, m)
            cash = project_cash_balance(current_cash, monthly_cash, m)
        
        total_downpayment = cpf + cash
        
        # Create a temporary loan eligibility object for max_loan
        from calculations import LoanEligibility, calculate_max_affordable_flat
        temp_eligibility = LoanEligibility(
            max_monthly_installment=0,
            max_loan_amount=max_loan,
            max_flat_price=max_loan / LTV_LIMIT,
            tenure_years=25,
            interest_rate=0.026,
            available_msr=0,
            total_commitments=0,
            exceeds_income_ceiling=False
        )
        
        # Use the proper calculation that accounts for stamp duty + legal fees
        max_affordable = calculate_max_affordable_flat(temp_eligibility, total_downpayment)
        max_affordable_prices.append(max_affordable)
    
    # Find where it plateaus (loan-limited)
    loan_limited_price = max_loan / LTV_LIMIT
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=months,
        y=max_affordable_prices,
        name="Max Affordable Flat",
        fill="tozeroy",
        line=dict(color=COLORS["primary"], width=3),
        hovertemplate="Month %{x}<br>Max Flat: $%{y:,.0f}<extra></extra>",
    ))
    
    # Loan ceiling line
    fig.add_hline(
        y=loan_limited_price,
        line=dict(color=COLORS["danger"], width=2, dash="dash"),
        annotation_text=f"Loan Limit: {format_currency(loan_limited_price)}",
        annotation_position="right",
    )
    
    fig.update_layout(
        title="Maximum Affordable Flat Price Over Time",
        xaxis_title="Months from Now",
        yaxis_title="Max Flat Price ($)",
        height=400,
        hovermode="x",
    )
    
    fig.update_yaxes(tickformat="$,.0f")
    
    return fig


# =============================================================================
# TENURE COMPARISON TABLE (for display)
# =============================================================================

def create_tenure_table_data(
    loan_amount: float,
    max_monthly_payment: float,
    interest_rate: float = HDB_INTEREST_RATE,
    key_tenures: list[int] = None
) -> list[dict]:
    """
    Generate data for tenure comparison table.
    
    Returns list of dicts with tenure info.
    """
    if key_tenures is None:
        key_tenures = [10, 15, 20, 25]
    
    interest_25yr = calculate_total_interest(loan_amount, interest_rate, 25)
    
    table_data = []
    for tenure in key_tenures:
        monthly = calculate_monthly_payment(loan_amount, interest_rate, tenure)
        total_interest = calculate_total_interest(loan_amount, interest_rate, tenure)
        
        table_data.append({
            "Tenure": f"{tenure} years",
            "Monthly Payment": format_currency(monthly),
            "Total Interest": format_currency(total_interest),
            "Interest Saved vs 25yr": format_currency(interest_25yr - total_interest),
            "Affordable": "✅" if monthly <= max_monthly_payment else "❌",
        })
    
    return table_data
