import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import os
from dotenv import load_dotenv
from datetime import datetime, date
from typing import Dict, Any

# --- PREMIUM CHART COLOR PALETTE ---
CHART_PALETTE = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#14B8A6', '#F43F5E', '#84CC16', '#6366F1', '#0EA5E9']

# --- UTILITY: Lifecycle Strategy ---
def get_lifecycle_strategy(birth_date_str):
    """Calculates age and returns the strategic allocation based on Lifecycle Phase."""
    try:
        from datetime import datetime, date
        birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except (ValueError, TypeError):
        age = 34 # Default fallback

    # Table Mapping
    if age < 40:
        return {
            'age': age,
            'phase': 'Phase: 34–40y - Maximum Growth',
            'acc': {'stocks': 93.0, 'bonds': 4.0, 'gold': 3.0},
            'div': {'stocks': 90.0, 'bonds': 7.0, 'gold': 3.0}
        }
    elif age < 45:
        return {
            'age': age,
            'phase': 'Phase: 40–45y - Balanced Growth',
            'acc': {'stocks': 91.0, 'bonds': 5.0, 'gold': 4.0},
            'div': {'stocks': 88.0, 'bonds': 8.0, 'gold': 4.0}
        }
    elif age < 50:
        return {
            'age': age,
            'phase': 'Phase: 45–50y - Defensive Growth',
            'acc': {'stocks': 88.0, 'bonds': 7.0, 'gold': 5.0},
            'div': {'stocks': 85.0, 'bonds': 10.0, 'gold': 5.0}
        }
    elif age < 55:
        return {
            'age': age,
            'phase': 'Phase: 50–55y - Moderate Protection',
            'acc': {'stocks': 85.0, 'bonds': 9.0, 'gold': 6.0},
            'div': {'stocks': 82.0, 'bonds': 12.0, 'gold': 6.0}
        }
    elif age < 60:
        return {
            'age': age,
            'phase': 'Phase: 55–60y - Capital Protection',
            'acc': {'stocks': 80.0, 'bonds': 12.0, 'gold': 8.0},
            'div': {'stocks': 80.0, 'bonds': 14.0, 'gold': 6.0}
        }
    elif age < 65:
        return {
            'age': age,
            'phase': 'Phase: 60–65y - Conservative',
            'acc': {'stocks': 75.0, 'bonds': 15.0, 'gold': 10.0},
            'div': {'stocks': 70.0, 'bonds': 18.0, 'gold': 12.0}
        }
    else: # 65-67+
        return {
            'age': age,
            'phase': 'Phase: 65–67y - Capital Preservation',
            'acc': {'stocks': 70.0, 'bonds': 20.0, 'gold': 10.0},
            'div': {'stocks': 60.0, 'bonds': 30.0, 'gold': 10.0}
        }


# =========================
# Unified Portfolio Helpers & Allocation Logic
# =========================

def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def round_weights(weights: Dict[str, float], decimals: int = 2) -> Dict[str, float]:
    return {asset: round(weight, decimals) for asset, weight in weights.items()}


def get_lifecycle_targets(age: int) -> Dict[str, float]:
    """
    Defines the strategic allocation by age.

    growth = SPYL / IXUA / VFEA block
    EGLN = gold
    PRAB = bonds / cash-like EUR government bonds 0-1y
    """

    if age < 40:
        return {
            "growth": 77.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 3.0,
            "PRAB.DE": 2.7,
        }

    elif age < 45:
        return {
            "growth": 74.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 4.0,
            "PRAB.DE": 4.7,
        }

    elif age < 50:
        return {
            "growth": 70.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 5.0,
            "PRAB.DE": 7.7,
        }

    elif age < 55:
        return {
            "growth": 66.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 6.0,
            "PRAB.DE": 10.7,
        }

    elif age < 60:
        return {
            "growth": 60.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 8.0,
            "PRAB.DE": 14.7,
        }

    elif age < 65:
        return {
            "growth": 54.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 10.0,
            "PRAB.DE": 18.7,
        }

    else:
        return {
            "growth": 47.0,
            "WTEQ.DE": 10.8,
            "VDIV.DE": 4.5,
            "JMT.PT": 1.0,
            "EDP.PT": 1.0,
            "EGLN.UK": 10.0,
            "PRAB.DE": 25.7,
        }


def calculate_growth_split(buffett_index: float) -> Dict[str, float]:
    """
    Calculates the allocation inside the growth block.

    Buffett <= 100  -> SPYL 70%
    Buffett ~165    -> SPYL 60%
    Buffett >= 230  -> SPYL 50%

    VFEA moves in stable steps:
    - SPYL >= 65 -> VFEA 10%
    - SPYL >= 55 -> VFEA 12.5%
    - SPYL < 55 -> VFEA 15%
    """

    SPYL_MIN = 50.0
    SPYL_MAX = 70.0

    BUFFETT_LOW = 100.0
    BUFFETT_HIGH = 230.0

    target_spyl = SPYL_MAX - (
        (buffett_index - BUFFETT_LOW) / (BUFFETT_HIGH - BUFFETT_LOW)
    ) * (SPYL_MAX - SPYL_MIN)

    target_spyl = round(clamp(target_spyl, SPYL_MIN, SPYL_MAX))

    if target_spyl >= 65.0:
        target_vfea = 10.0
    elif target_spyl >= 55.0:
        target_vfea = 12.5
    else:
        target_vfea = 15.0

    target_ixua = 100.0 - target_spyl - target_vfea

    return {
        "SPYL.DE": target_spyl,
        "IXUA.DE": target_ixua,
        "VFEA.DE": target_vfea,
    }


def calculate_portfolio_targets(age: int, buffett_index: float) -> Dict[str, Any]:
    """
    Calculates final portfolio target weights.

    Returns:
    - lifecycle allocation
    - growth split
    - final portfolio target weights
    """

    lifecycle = get_lifecycle_targets(age)
    growth_weight = lifecycle["growth"]

    growth_split = calculate_growth_split(buffett_index)

    spyl_target = round(growth_weight * growth_split["SPYL.DE"] / 100.0, 2)
    vfea_target = round(growth_weight * growth_split["VFEA.DE"] / 100.0, 2)
    ixua_target = round(growth_weight - spyl_target - vfea_target, 2)

    targets = {
        "SPYL.DE": spyl_target,
        "IXUA.DE": ixua_target,
        "VFEA.DE": vfea_target,
        "WTEQ.DE": lifecycle["WTEQ.DE"],
        "VDIV.DE": lifecycle["VDIV.DE"],
        "JMT.PT": lifecycle["JMT.PT"],
        "EDP.PT": lifecycle["EDP.PT"],
        "EGLN.UK": lifecycle["EGLN.UK"],
        "PRAB.DE": lifecycle["PRAB.DE"],
    }

    total = sum(targets.values())

    if abs(total - 100.0) > 0.01:
        raise ValueError(f"Portfolio targets do not sum to 100%. Total = {total:.2f}%")

    return {
        "age": age,
        "buffett_index": buffett_index,
        "lifecycle": lifecycle,
        "growth_split": growth_split,
        "targets": round_weights(targets, 2),
        "total": round(total, 2),
    }


TOLERANCE_PP = {
    "SPYL.DE": 3.0,
    "IXUA.DE": 3.0,
    "VFEA.DE": 1.5,
    "WTEQ.DE": 2.0,
    "VDIV.DE": 2.0,
    "JMT.PT": 1.0,
    "EDP.PT": 1.0,
    "EGLN.UK": 1.0,
    "PRAB.DE": 0.5,
}


def calculate_egln_prab_transition_plan(
    portfolio_value: float,
    monthly_contribution: float,
    current_egln_value: float = 0.0,
    current_prab_value: float = 0.0,
    months: int = 4,
    egln_target_pct: float = 3.0,
    prab_target_pct: float = 2.7,
    min_order_size: float = 5.0,
):
    plan = []

    egln_value = current_egln_value
    prab_value = current_prab_value
    current_portfolio_value = portfolio_value

    for month in range(1, months + 1):
        portfolio_after_contribution = current_portfolio_value + monthly_contribution

        egln_target_value = portfolio_after_contribution * egln_target_pct / 100.0
        prab_target_value = portfolio_after_contribution * prab_target_pct / 100.0

        months_left = months - month + 1

        egln_gap = max(0.0, egln_target_value - egln_value)
        prab_gap = max(0.0, prab_target_value - prab_value)

        egln_buy = egln_gap / months_left
        prab_buy = prab_gap / months_left

        if egln_buy < min_order_size:
            egln_buy = 0.0

        if prab_buy < min_order_size:
            prab_buy = 0.0

        total_defensive_buy = egln_buy + prab_buy
        remaining_for_normal_strategy = monthly_contribution - total_defensive_buy

        egln_value += egln_buy
        prab_value += prab_buy
        current_portfolio_value = portfolio_after_contribution

        plan.append({
            "month": month,
            "portfolio_after_contribution": round(portfolio_after_contribution, 2),
            "egln_buy": round(egln_buy, 2),
            "prab_buy": round(prab_buy, 2),
            "remaining_for_normal_strategy": round(remaining_for_normal_strategy, 2),
            "egln_value_after_buy": round(egln_value, 2),
            "prab_value_after_buy": round(prab_value, 2),
            "egln_target_value": round(egln_target_value, 2),
            "prab_target_value": round(prab_target_value, 2),
        })

    return plan


def calculate_monthly_buys(
    age: int,
    buffett_index: float,
    current_values: Dict[str, float],
    monthly_contribution: float,
    min_order_size: float = 5.0,
    exclude_defensive: bool = False,
) -> Dict[str, Any]:
    """
    Calculates how to allocate the monthly contribution.

    Rules:
    - Never sell.
    - Only buy assets below their tolerance band.
    - Ignore orders below min_order_size.
    - Leftover cash is returned.
    """

    portfolio_data = calculate_portfolio_targets(age, buffett_index)
    targets = portfolio_data["targets"]

    if exclude_defensive:
        targets = targets.copy()
        def_sum = targets.get("EGLN.UK", 0.0) + targets.get("PRAB.DE", 0.0)
        remaining_sum = 100.0 - def_sum
        for asset in list(targets.keys()):
            if asset in ("EGLN.UK", "PRAB.DE"):
                targets[asset] = 0.0
            elif remaining_sum > 0:
                targets[asset] = (targets[asset] / remaining_sum) * 100.0

    all_assets = list(targets.keys())

    portfolio_value = sum(current_values.get(asset, 0.0) for asset in all_assets)

    if portfolio_value < 0:
        raise ValueError("Portfolio value cannot be negative.")

    if monthly_contribution <= 0:
        raise ValueError("Monthly contribution must be positive.")

    # If portfolio is empty, buy according to target weights
    if portfolio_value == 0:
        raw_buys = {
            asset: monthly_contribution * targets[asset] / 100.0
            for asset in all_assets
        }

        # Apply minimum order size and round down to integer euros
        import math
        rounded_buys = {}
        total_rounded = 0.0
        for asset, amount in raw_buys.items():
            if amount >= min_order_size:
                rounded_val = float(math.floor(amount))
                rounded_buys[asset] = rounded_val
                total_rounded += rounded_val
            else:
                rounded_buys[asset] = 0.0

        # Redistribution of Cents ("The Dump")
        leftover_cash = 0.0
        if any(rounded_buys.values()):
            dump_ticker = max(rounded_buys, key=rounded_buys.get)
            remaining_budget = monthly_contribution - total_rounded
            if remaining_budget > 0:
                rounded_buys[dump_ticker] += remaining_budget
            leftover_cash = 0.0
        else:
            leftover_cash = monthly_contribution

        buys = rounded_buys

        return {
            "age": age,
            "buffett_index": buffett_index,
            "portfolio_value_before": 0.0,
            "monthly_contribution": round(monthly_contribution, 2),
            "portfolio_value_after": round(monthly_contribution, 2),
            "portfolio_targets": targets,
            "current_weights": {asset: 0.0 for asset in all_assets},
            "raw_buys": round_weights(raw_buys, 2),
            "buys": round_weights(buys, 2),
            "leftover_cash": round(leftover_cash, 2),
        }

    # Current weights before contribution
    current_weights = {
        asset: current_values.get(asset, 0.0) / portfolio_value * 100.0
        for asset in all_assets
    }

    # Portfolio value after new contribution
    new_total_value = portfolio_value + monthly_contribution

    # Target value after contribution
    target_values_after_contribution = {
        asset: new_total_value * targets[asset] / 100.0
        for asset in all_assets
    }

    # Value gaps to target
    value_gaps = {
        asset: max(
            0.0,
            target_values_after_contribution[asset] - current_values.get(asset, 0.0)
        )
        for asset in all_assets
    }

    # Percentage gaps before contribution
    percentage_gaps = {
        asset: max(0.0, targets[asset] - current_weights[asset])
        for asset in all_assets
    }

    # Only eligible if below tolerance band
    eligible_gaps = {
        asset: value_gaps[asset]
        for asset in all_assets
        if percentage_gaps[asset] >= TOLERANCE_PP[asset]
    }

    total_eligible_gap = sum(eligible_gaps.values())

    if total_eligible_gap > 0:
        raw_buys = {
            asset: monthly_contribution * eligible_gaps.get(asset, 0.0) / total_eligible_gap
            for asset in all_assets
        }
    else:
        # If nothing is materially below target, invest according to target weights
        raw_buys = {
            asset: monthly_contribution * targets[asset] / 100.0
            for asset in all_assets
        }

    # Apply minimum order size and round down to integer euros
    import math
    rounded_buys = {}
    total_rounded = 0.0
    for asset, amount in raw_buys.items():
        if amount >= min_order_size:
            rounded_val = float(math.floor(amount))
            rounded_buys[asset] = rounded_val
            total_rounded += rounded_val
        else:
            rounded_buys[asset] = 0.0

    # Redistribution of Cents ("The Dump")
    # All remaining contribution goes into the ticker with the highest investment
    leftover_cash = 0.0
    if any(rounded_buys.values()):
        dump_ticker = max(rounded_buys, key=rounded_buys.get)
        remaining_budget = monthly_contribution - total_rounded
        if remaining_budget > 0:
            rounded_buys[dump_ticker] += remaining_budget
        leftover_cash = 0.0
    else:
        leftover_cash = monthly_contribution

    buys = rounded_buys

    return {
        "age": age,
        "buffett_index": buffett_index,
        "portfolio_value_before": round(portfolio_value, 2),
        "monthly_contribution": round(monthly_contribution, 2),
        "portfolio_value_after": round(new_total_value, 2),
        "portfolio_targets": targets,
        "current_weights": round_weights(current_weights, 2),
        "percentage_gaps": round_weights(percentage_gaps, 2),
        "eligible_assets": list(eligible_gaps.keys()),
        "raw_buys": round_weights(raw_buys, 2),
        "buys": round_weights(buys, 2),
        "leftover_cash": round(leftover_cash, 2),
    }



# Load environment variables
load_dotenv(override=True)

st.set_page_config(page_title="Portfolio Manager", page_icon="🚀", layout="wide")

# --- Dashboard Redesign Styling ---
st.markdown("""
<style>
    /* Global Background & Variables */
    :root {
        --primary-accent: #10B981; /* Emerald Green */
        --primary-hover: #059669;
        --bg-dark: #1E1E2E;
        --sidebar-light: #D1D5DB; /* Slightly Darker Grey */
        --card-dark: #2D2D3A;
        --text-light: #F8FAFC;
        --text-sidebar: #1F2937; /* Dark Charcoal */
    }

    .stApp {
        background-color: var(--bg-dark);
    }
    
    /* Increase Tabs Font Size */
    button[data-baseweb="tab"] p {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
    }
    button[data-baseweb="tab"] div {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
    }

    /* Sidebar Styling (Light Mode) */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-light);
        border-right: 1px solid rgba(0,0,0,0.05);
    }
    
    /* Input Labels in Sidebar (Dark Text) */
    [data-testid="stSidebar"] label p {
        color: var(--text-sidebar) !important;
        font-weight: 500 !important;
    }

    /* High-Visibility Sidebar Toggle (Show/Hide) */
    button[data-testid="stBaseButton-header"],
    button[data-testid="stBaseButton-headerNoPadding"],
    [data-testid="stSidebarCollapsedControl"] button {
        background-color: var(--primary-accent) !important;
        color: white !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4) !important;
    }
    
    button[data-testid="stBaseButton-header"]:hover,
    button[data-testid="stBaseButton-headerNoPadding"]:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover {
        background-color: var(--primary-hover) !important;
        transform: scale(1.1) !important;
    }

    button[data-testid="stBaseButton-header"] svg,
    button[data-testid="stBaseButton-headerNoPadding"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        fill: white !important;
        color: white !important;
    }
    
    /* Selectbox/Input values in sidebar */
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] .stNumberInput input,
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] {
        color: var(--text-sidebar) !important;
        background-color: white !important;
        border-radius: 8px !important;
    }

    /* Fix sidebar number input controls (+/-) visibility */
    [data-testid="stSidebar"] .stNumberInput div[data-baseweb="input"] {
        background-color: white !important;
    }
    
    [data-testid="stSidebar"] .stNumberInput button {
        background-color: #F3F4F6 !important;
        color: var(--text-sidebar) !important;
        border: none !important;
    }

    /* Fix selection text in sidebar inputs */
    /* Fix selection text in sidebar inputs - Remove contours globally (Aggressive) */
    /* Fix selection text in sidebar inputs - Remove contours globally (Aggressive) */
    [data-testid="stSidebar"] input,
    
    /* Target various containers to ensure background consistency */
    [data-testid="stSidebar"] div[data-baseweb="select"] > div,
    [data-testid="stSidebar"] div[data-testid="stTextInput"] > div,
    [data-testid="stSidebar"] div[data-testid="stNumberInput"] > div,
    [data-testid="stSidebar"] div[data-baseweb="input"],
    [data-testid="stSidebar"] div[data-baseweb="base-input"] {
        background-color: white !important;
        border-radius: 8px !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        /* Force dark text and caret for visibility on white background */
        color: #31333F !important;
        caret-color: #31333F !important;
    }
    
    /* Ensure selection is visible within sidebar inputs */
    [data-testid="stSidebar"] input::selection {
        background-color: rgba(46, 204, 113, 0.4) !important; /* Primary accent fade */
        color: #31333F !important;
    }
    
    /* Target specific inner elements to ensure no internal borders */
    [data-testid="stSidebar"] .stNumberInput input,
    [data-testid="stSidebar"] .stTextInput input {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
    }

    /* Remove borders from the buttons inside number inputs */
    [data-testid="stSidebar"] .stNumberInput button {
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
        border-left: 1px solid transparent !important; 
    }

    /* Expander Styling in Sidebar - Align with white inputs for maximum contrast */
    [data-testid="stSidebar"] details {
        border: 1px solid rgba(0,0,0,0.05) !important;
        border-radius: 12px !important;
        background-color: rgba(0,0,0,0.02) !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }
    
    [data-testid="stSidebar"] details summary {
        background-color: transparent !important;
        color: var(--text-sidebar) !important;
        padding: 5px 10px !important;
    }
    
    [data-testid="stSidebar"] details summary:hover {
        background-color: rgba(255,255,255,0.05) !important;
    }

    [data-testid="stSidebar"] details summary p {
        color: var(--text-sidebar) !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }

    /* Explicitly target expander chevron icons */
    [data-testid="stSidebar"] details summary svg,
    [data-testid="stSidebar"] details summary svg * {
        fill: var(--text-sidebar) !important;
        stroke: var(--text-sidebar) !important;
        color: var(--text-sidebar) !important;
    }

    /* Sidebar Checkbox Styling - Clean and minimal */
    [data-testid="stSidebar"] .stCheckbox,
    [data-testid="stSidebar"] .stCheckbox > label,
    [data-testid="stSidebar"] .stCheckbox label > div,
    [data-testid="stSidebar"] .stCheckbox label > div > div {
        background-color: transparent !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }
    
    [data-testid="stSidebar"] .stCheckbox > label {
        color: var(--text-sidebar) !important;
    }
    
    /* Checkbox Styling - Split Approach (Iteration 5) */
    
    /* 1. The Container (Label) - Ensure transparent */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] {
        background-color: transparent !important;
    }

    /* 2. The Visual Box (First Child) - White when unchecked */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:first-child {
        background-color: white !important;
        border: 1px solid #9CA3AF !important;
        border-radius: 3px !important;
    }
    
    /* 3. The Text Label (Last Child) - Transparent */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:last-child {
        background-color: transparent !important;
        color: var(--text-sidebar) !important;
    }

    /* 4. CHECKED State for the Box Only */
    [data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:first-child[aria-checked="true"],
    [data-testid="stSidebar"] [data-baseweb="checkbox"][aria-checked="true"] > div:first-child {
        background-color: var(--primary-accent) !important;
        border-color: var(--primary-accent) !important;
    }
    
    /* Ensure inner checkmark is visible when checked */
    [data-testid="stSidebar"] [aria-checked="true"] svg {
        fill: white !important;
    }
    
    /* Ensure unchecked checkmark is invisible */
    [data-testid="stSidebar"] [aria-checked="false"] svg {
        fill: transparent !important;
    }
    
    /* Unchecked checkbox - make inner checkmark SVG invisible (only direct child) */
    [data-testid="stSidebar"] [data-baseweb="checkbox"]:not([aria-checked="true"]) > div > svg {
        fill: none !important;
        stroke: none !important;
        opacity: 0 !important;
    }
    
    /* Checked checkbox - emerald green with white checkmark */
    [data-testid="stSidebar"] [data-baseweb="checkbox"][aria-checked="true"] > div {
        background-color: var(--primary-accent) !important;
        border-color: var(--primary-accent) !important;
    }
    
    [data-testid="stSidebar"] [data-baseweb="checkbox"][aria-checked="true"] > div > svg {
        fill: white !important;
        opacity: 1 !important;
    }

    /* Help Icons (?) in sidebar - simple dark icons */
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"],
    [data-testid="stSidebar"] .stCheckbox [data-testid="stTooltipIcon"] {
        color: var(--text-sidebar) !important;
        opacity: 1 !important;
        visibility: visible !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        background-color: transparent !important;
        border: none !important;
        margin-left: 4px !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg,
    [data-testid="stSidebar"] .stCheckbox [data-testid="stTooltipIcon"] svg {
        fill: var(--text-sidebar) !important;
        opacity: 1 !important;
        visibility: visible !important;
    }

    /* Sidebar Dividers */
    [data-testid="stSidebar"] hr {
        border-color: rgba(0,0,0,0.05) !important;
    }

    /* Dataframe row separators - ensure borders are visible on all cells */
    [data-testid="stDataFrame"] td {
        border-bottom: 1px solid rgba(255,255,255,0.1) !important;
    }

    /* Sidebar Headers & General Text - Universal Dark (Aggressive Targeting) */
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] div,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] em,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h4,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h5,
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h6,
    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text-sidebar) !important;
    }


    /* Sidebar Alerts/Info boxes */
    [data-testid="stSidebar"] div[data-testid="stNotification"] {
        background-color: rgba(0, 0, 0, 0.03) !important;
        border: 1px solid rgba(0, 0, 0, 0.05) !important;
    }
    
    /* Sidebar Alerts/Info boxes (Aggressive targeting for text visibility) */
    [data-testid="stSidebar"] div[data-testid="stNotification"] div,
    [data-testid="stSidebar"] div[data-testid="stNotification"] p,
    [data-testid="stSidebar"] div[data-testid="stNotification"] strong,
    [data-testid="stSidebar"] div[data-testid="stNotification"] span {
        color: var(--text-sidebar) !important;
    }

    /* EXPLICIT BUTTON TEXT PROTECTION IN SIDEBAR */
    [data-testid="stSidebar"] button p,
    [data-testid="stSidebar"] .stButton button p,
    [data-testid="stSidebar"] .stButton button span {
        color: white !important;
    }



    /* Target Streamlit's native containers for the "Card" look */
    /* This styles st.container(border=True) */
    [data-testid="stElementContainer"] > div:has(div.stVerticalBlockBorder) {
        background-color: var(--card-dark) !important;
        border-radius: 15px !important;
        padding: 24px !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2) !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        margin-bottom: 20px !important;
    }

    /* KPI Metric Cards (Custom CSS for our HTML injection) */
    .kpi-card {
        background-color: var(--card-dark);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255,255,255,0.05);
        text-align: left;
        margin-bottom: 15px;
    }
    .kpi-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94A3B8;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .kpi-value {
        font-size: 1.7rem;
        font-weight: 800;
        color: var(--text-light);
    }

    /* Primary Buttons (Emerald) */
    div.stButton > button:first-child {
        background-color: var(--primary-accent);
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    div.stButton > button:first-child:hover {
        background-color: var(--primary-hover);
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    
        /* Danger Buttons (for Remove) - Centered Emoji */
    div.stButton button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    div.stButton button p {
        width: auto !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* Specifically for remove buttons (red cross) */
    div[data-testid="stButton"] button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    div[data-testid="stButton"] button p {
        width: auto !important;
        margin: 0 !important;
        flex: 1 !important;
        text-align: center !important;
    }


    div[data-testid="stButton"]:has(button:contains("❌")) button:hover,
    .danger-btn div.stButton > button:first-child:hover {
        background-color: #FCA5A5 !important;
        box-shadow: 0 4px 12px rgba(239, 68, 68, 0.2) !important;
    }

    /* Target specific inputs in the management table for better alignment */
    [data-testid="stVerticalBlock"] .stNumberInput input,
    [data-testid="stVerticalBlock"] .stTextInput input {
        padding-top: 5px !important;
        padding-bottom: 5px !important;
        height: 38px !important;
    }

    /* Main App Content - Universal White for Dark Mode (Robust Targeting) */
    [data-testid="stAppViewContainer"] h1, 
    [data-testid="stAppViewContainer"] h2, 
    [data-testid="stAppViewContainer"] h3, 
    [data-testid="stAppViewContainer"] h4, 
    [data-testid="stAppViewContainer"] h5, 
    [data-testid="stAppViewContainer"] h6,
    [data-testid="stAppViewContainer"] p, 
    [data-testid="stAppViewContainer"] label, 
    [data-testid="stAppViewContainer"] span, 
    [data-testid="stAppViewContainer"] .stMarkdown {
        color: var(--text-light) !important;
    }

    /* Custom Headers for Main Content */
    h1, h2, h3 {
        color: var(--text-light) !important;
        font-weight: 800;
    }

    /* Hide standard Streamlit extras but keep the header for the sidebar toggle */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stHeader"] > div {
        visibility: visible !important;
    }
    /* Specifically hide the deploy button and other header junk */
    [data-testid="stHeader"] button[data-testid="stBaseButton-secondary"],
    [data-testid="stHeader"] div[data-testid="stStatusWidget"] {
        display: none !important;
    }

    /* Profit color overrides with extreme specificity placed at the very bottom */
    [data-testid="stAppViewContainer"] div.kpi-card span.profit-green,
    [data-testid="stAppViewContainer"] span.profit-green {
        color: #10B981 !important;
        font-weight: 800 !important;
    }
    [data-testid="stAppViewContainer"] div.kpi-card span.profit-red,
    [data-testid="stAppViewContainer"] span.profit-red {
        color: #EF4444 !important;
        font-weight: 800 !important;
    }
</style>
""", unsafe_allow_html=True)

def render_kpi_card(label, value):
    st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
    """, unsafe_allow_html=True)

# --- User Authentication ---
if 'authentication_status' not in st.session_state:
    st.session_state['authentication_status'] = None
if 'has_unsaved_changes' not in st.session_state:
    st.session_state.has_unsaved_changes = False
if 'saved_manual_targets' not in st.session_state:
    st.session_state['saved_manual_targets'] = {}
if 'show_recommendations' not in st.session_state:
    st.session_state.show_recommendations = False
if 'last_calculation' not in st.session_state:
    st.session_state.last_calculation = None
if 'show_save_success' not in st.session_state:
    st.session_state.show_save_success = False
if 'undo_buffer' not in st.session_state:
    st.session_state.undo_buffer = []
if 'show_undo' not in st.session_state:
    st.session_state.show_undo = False
if 'editor_key' not in st.session_state:
    st.session_state.editor_key = 0

def clear_recommendations():
    st.session_state.show_recommendations = False
    st.session_state.show_save_success = False
    st.session_state.last_calculation = None

def calculate_kids_targets(birth_date_str):
    if not birth_date_str or not isinstance(birth_date_str, str):
        return None
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = datetime.today().date()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        if age <= 13:
            return {"VWCE.DE": 100.0, "VAGF.DE": 0.0}
        elif age == 14:
            return {"VWCE.DE": 95.0, "VAGF.DE": 5.0}
        elif age == 15:
            return {"VWCE.DE": 90.0, "VAGF.DE": 10.0}
        elif age == 16:
            return {"VWCE.DE": 85.0, "VAGF.DE": 15.0}
        elif age == 17:
            return {"VWCE.DE": 80.0, "VAGF.DE": 20.0}
        elif age >= 18:
            return {"VWCE.DE": 70.0, "VAGF.DE": 30.0}
    except Exception:
        return None
    return None

def reset_portfolio_state():
    clear_recommendations()
    if 'portfolio_selector' in st.session_state:
        selected = st.session_state.portfolio_selector
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"{selected}_")]
        for k in keys_to_clear:
            del st.session_state[k]
    # Force re-sync of stocks state on next run
    if 'last_selected_portfolio' in st.session_state:
        del st.session_state.last_selected_portfolio

# Get secrets
admin_hash = os.getenv('ADMIN_PASSWORD_HASH')
cookie_key = os.getenv('COOKIE_KEY')

if not admin_hash or not cookie_key:
    st.error("security configuration missing: ADMIN_PASSWORD_HASH or COOKIE_KEY not found in environment.")
    st.stop()

# Configuration dictionary
config = {
    'credentials': {
        'usernames': {
            'admin': {
                'name': 'Admin User',
                'password': admin_hash,
                'email': 'admin@example.com'
            }
        }
    },
    'cookie': {
        'name': 'portfolio_rebalancer_cookie',
        'key': cookie_key,
        'expiry_days': 30
    },
    'pre-authorized': {'emails': []}
}

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

authenticator.login('main')

authentication_status = st.session_state.get('authentication_status')
name = st.session_state.get('name')
username = st.session_state.get('username')

if authentication_status is False:
    st.error('Username/password is incorrect')
elif authentication_status is None:
    st.warning('Please enter your username and password')
elif authentication_status:
    # --- Main Title (Top Level) ---
    st.title("🚀 Portfolio Manager: Allocation & Analytics")
    st.markdown("Optimization, Dividend Tracking, and Portfolio Analytics")
    # st.divider()

    # Initialize GSheets connection
    # pyrefly: ignore [missing-import]
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Load data from Google Sheets into Session State
    if 'master_data' not in st.session_state:
        try:
            # Load with a cache but then move to Session State for "instant" local updates
            raw_data = conn.read(worksheet="Portfolios", ttl="10m") 
            
            if raw_data is None:
                raw_data = pd.DataFrame()
                
            if not raw_data.empty and 'portfolio_name' not in raw_data.columns:
                raw_data['portfolio_name'] = 'Default'
            
            required_columns = [
                'username', 'stock_name', 'current_value', 'target_allocation', 
                'portfolio_name', 'tolerance', 'expense_ratio', 'portfolio_monthly_invest', 
                'portfolio_use_indicators', 'portfolio_buffett_index',
                'stock_full_name', 'sector', 'industry', 'country', 'currency', 
                'quantity', 'average_price', 'dividend_yield', 'portfolio_type',
                'portfolio_birth_date', 'portfolio_uninvested_cash', 'current_price', 'investor_birth_date'
            ]
            
            if raw_data.empty:
                raw_data = pd.DataFrame(columns=required_columns)
            else:
                for col in required_columns:
                    if col not in raw_data.columns:
                        if col == 'portfolio_monthly_invest': raw_data[col] = 1000.0
                        elif col == 'portfolio_use_indicators': raw_data[col] = False
                        elif col == 'portfolio_buffett_index': raw_data[col] = 195.0
                        elif col == 'portfolio_type': raw_data[col] = 'Other'
                        elif col == 'portfolio_birth_date': raw_data[col] = ''
                        elif col == 'portfolio_uninvested_cash': raw_data[col] = 0.0
                        elif col == 'investor_birth_date': raw_data[col] = '1992-01-01' # Default starting point (34y approx)
                        elif col in ['current_value', 'target_allocation', 'tolerance', 'expense_ratio', 'quantity', 'average_price', 'dividend_yield', 'current_price']: raw_data[col] = 0.0
                        else: raw_data[col] = ''
                        
                raw_data = raw_data.astype({
                    'username': 'str',
                    'stock_name': 'str', 
                    'current_value': 'float',
                    'target_allocation': 'float',
                    'expense_ratio': 'float',
                    'portfolio_name': 'str',
                    'current_price': 'float'
                })
                raw_data['portfolio_name'] = raw_data['portfolio_name'].fillna('Default')
                raw_data['username'] = raw_data['username'].fillna('unknown') 

            st.session_state.master_data = raw_data

            # Load Dividends Data
            if 'dividends' not in st.session_state:
                try:
                    div_data = conn.read(worksheet="Dividends", ttl=0)
                    if div_data is None or div_data.empty:
                        div_data = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])
                    # Ensure columns exist
                    for col in ['date', 'ticker', 'amount', 'portfolio_name', 'username']:
                        if col not in div_data.columns:
                            div_data[col] = '' if col in ['date', 'ticker', 'portfolio_name', 'username'] else 0.0
                    st.session_state.dividends = div_data
                except Exception:
                     # Worksheet likely doesn't exist yet
                    st.session_state.dividends = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])

        except Exception as e:
            st.session_state.master_data = pd.DataFrame(columns=['username', 'stock_name', 'current_value', 'target_allocation', 'portfolio_name'])

    data = st.session_state.master_data

    with st.sidebar:
        # 1. Logout & Welcome
        authenticator.logout('Logout', 'main')
        st.write(f'Welcome *{name}*')
        
        # 1. Global Total Invested
        user_all_data = data[data['username'] == username] if not data.empty else pd.DataFrame()
        
        global_total = 0.0
        merged_global = pd.DataFrame()
        
        if not user_all_data.empty:
            valid_data = user_all_data[user_all_data['stock_name'] != '__PLACEHOLDER__'].copy()
            
            # Exclude Kids portfolios from global overview and sidebar total values
            global_valid_data = valid_data[valid_data['portfolio_type'].str.strip().str.upper() != "KIDS"].copy()
            
            # Separate Gold, Bonds, Growth, and Dividends based on user asset categories
            growth_tickers = {"SPYL.DE", "IXUA.DE", "VFEA.DE"}
            dividend_tickers = {"WTEQ.DE", "VDIV.DE", "EDP.PT", "JMT.PT"}
            gold_tickers = {"EGLN.UK", "EGNL.UK"}
            bond_tickers = {"PRAB.DE", "IBTE.UK"}

            def assign_global_label(row):
                ticker = str(row['stock_name']).upper().strip()
                p_type = str(row['portfolio_type']).strip()
                p_name = str(row['portfolio_name']).strip()
                
                # Gold and Bonds are separated globally across all portfolios
                if ticker in gold_tickers:
                    return "Gold"
                if ticker in bond_tickers:
                    return "Bonds"
                
                # Split Growth & Dividends (Unified Portfolio) assets
                if p_type == "Unified" or "growth" in p_name.lower():
                    if ticker in growth_tickers:
                        return "Growth"
                    if ticker in dividend_tickers:
                        return "Dividends"
                        
                return row['portfolio_name']

            global_valid_data['portfolio_name'] = global_valid_data.apply(assign_global_label, axis=1)
            
            merged_global = global_valid_data.groupby('portfolio_name')['current_value'].sum().reset_index()
            merged_global.rename(columns={'current_value': 'total_value'}, inplace=True)
            merged_global = merged_global[merged_global['total_value'] > 0]
            
            global_total = merged_global['total_value'].sum()

        st.markdown(
            f"""
            <style>
            .green-text-force {{
                color: #10B981 !important;
                -webkit-text-fill-color: #10B981 !important;
                font-size: 2.2rem !important;
                font-weight: 900 !important;
            }}
            </style>
            <div style="padding-top: 10px; line-height: 1.2;">
                <div style="color: #1f2937; font-size: 1.8rem; font-weight: 800;">💶 Total Value</div>
                <div class="green-text-force" style="color: #10B981 !important; font-size: 2.2rem !important; font-weight: 900 !important; padding-left: 2.3rem; margin-top: -5px;">€{global_total:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.divider()

    # --- Data Filtering & Initialization (Top Level) ---

    # Determine existing portfolios
    if not user_all_data.empty:
        existing_portfolios = sorted(user_all_data['portfolio_name'].unique().tolist())
    else:
        existing_portfolios = []
    portfolio_options = ["🌍 Global Overview"] + existing_portfolios
    
    # Handle auto-selection after creation
    default_index = 0
    if 'new_portfolio_created' in st.session_state:
        target_new = st.session_state.new_portfolio_created
        if target_new in existing_portfolios:
            default_index = existing_portfolios.index(target_new) + 1
        # We don't delete it yet, we need it for the widget default
    elif st.session_state.get('last_selected_portfolio') in portfolio_options:
        default_index = portfolio_options.index(st.session_state.get('last_selected_portfolio'))
    
    # We need a temporary key for the selector to avoid duplication issues if we move it
    selected_portfolio = None
    if existing_portfolios:
        # We peek at the session state to see if there's a selected portfolio already
        # but since we haven't rendered the selectbox yet, we use the logic below.
        pass

    # --- Sidebar UI ---
    with st.sidebar:


        # 1. Portfolios Section
        with st.expander("📂 Portfolios", expanded=True):
            if portfolio_options:
                def format_portfolio_name(p_name):
                    if p_name == "🌍 Global Overview": return p_name
                    name_lower = p_name.lower()
                    if "grow" in name_lower or "accum" in name_lower:
                        return f"🌱 {p_name}"
                    if "dividend" in name_lower:
                        return f"💸 {p_name}"

                    if user_all_data.empty: return p_name
                    p_rows = user_all_data[user_all_data['portfolio_name'] == p_name]
                    if p_rows.empty: return p_name
                    p_type = p_rows['portfolio_type'].iloc[0]
                    
                    if p_type == "Stocks": return f"📈 {p_name}"
                    elif p_type == "Kids": return f"🧸 {p_name}"
                    elif p_type == "Unified": return f"🏛️ {p_name}"
                    return f"📁 {p_name}"

                selected_portfolio = st.selectbox(
                    "Select View", 
                    portfolio_options, 
                    index=default_index, 
                    key="portfolio_selector",
                    format_func=format_portfolio_name,
                    on_change=reset_portfolio_state
                )
                # If a new portfolio was just created and we just rendered the selectbox with it, we can clear the flag
                if 'new_portfolio_created' in st.session_state and st.session_state.new_portfolio_created == selected_portfolio:
                    del st.session_state.new_portfolio_created
            else:
                selected_portfolio = None
                st.info("No portfolios found.")
            
            # Create New Portfolio
            with st.expander("➕ Create New Portfolio"):
                new_portfolio_input = st.text_input("Name", placeholder="e.g., Accumulation", key="new_p_name")
                new_portfolio_type = st.selectbox("Type", options=["Stocks", "Kids", "Unified"], index=2, key="new_p_type")
                if st.button("Create"):
                    if new_portfolio_input and new_portfolio_input not in existing_portfolios:
                        # Create a placeholder row to persist the portfolio name
                        new_row = pd.DataFrame([{
                            "username": username,
                            "portfolio_name": new_portfolio_input,
                            "stock_name": "__PLACEHOLDER__",
                            "current_value": 0.0,
                            "target_allocation": 0.0,
                            "portfolio_type": new_portfolio_type,
                            "portfolio_birth_date": ""
                        }])
                        updated_data = pd.concat([data, new_row], ignore_index=True)
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)
                        
                        st.session_state.new_portfolio_created = new_portfolio_input
                        st.session_state.has_unsaved_changes = False # Just synced
                        reset_portfolio_state()
                        st.success(f"Created '{new_portfolio_input}'!")
                        st.rerun()
                    elif new_portfolio_input in existing_portfolios:
                        st.error("A portfolio with this name already exists.")
                    else:
                        st.error("Please enter a valid name.")


            # Rename Portfolio
            if selected_portfolio and selected_portfolio != "🌍 Global Overview":
                with st.expander(f"⚙️ Portfolio Settings"):
                    # Get current type for default
                    current_type = user_all_data[user_all_data['portfolio_name'] == selected_portfolio]['portfolio_type'].iloc[0] if not user_all_data[user_all_data['portfolio_name'] == selected_portfolio].empty else "Unified"
                    type_options = ["Stocks", "Kids", "Unified"]
                    type_index = type_options.index(current_type) if current_type in type_options else 2

                    new_name_input = st.text_input("Rename Portfolio", value=selected_portfolio, placeholder="e.g., accumulation 2026")
                    new_type_input = st.selectbox("Portfolio Type", options=type_options, index=type_index)
                    
                    if st.button("Save Settings"):
                        # Check if name changed and if new name already exists
                        name_changed = new_name_input != selected_portfolio
                        type_changed = new_type_input != current_type

                        if name_changed and new_name_input in existing_portfolios:
                            st.error("A portfolio with this name already exists.")
                        elif name_changed or type_changed:
                            # Update all rows in master data
                            mask = (st.session_state.master_data['username'] == username) & \
                                   (st.session_state.master_data['portfolio_name'] == selected_portfolio)
                            
                            updated_data = st.session_state.master_data.copy()
                            
                            if name_changed:
                                updated_data.loc[mask, 'portfolio_name'] = new_name_input
                                final_name = new_name_input
                            else:
                                final_name = selected_portfolio
                                
                            if type_changed:
                                updated_data.loc[mask, 'portfolio_type'] = new_type_input
                                
                            st.session_state.master_data = updated_data
                            conn.update(worksheet="Portfolios", data=updated_data)
                            st.session_state.has_unsaved_changes = False # Just synced
                            reset_portfolio_state()
                            
                            st.session_state.new_portfolio_created = final_name # Use this to auto-select renamed portfolio
                            st.success(f"Settings saved for '{final_name}'!")
                            st.rerun()
                        else:
                            st.error("Please enter a valid name.")

            # Delete Portfolio
            if selected_portfolio and selected_portfolio != "🌍 Global Overview":
                with st.expander(f"⚠️ Delete '{selected_portfolio}'"):
                    st.warning("This action cannot be undone.")
                    if st.button("Confirm Delete", type="primary", key="delete_portfolio_btn"):
                        # Remove all rows belonging to this portfolio
                        mask_to_delete = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        updated_data = data[~mask_to_delete]
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)
                        st.session_state.has_unsaved_changes = False # Just synced
                        reset_portfolio_state()
                        st.toast(f"Deleted portfolio: {selected_portfolio}")
                        st.rerun()
        
    # --- Sync Data Logic (Source of Truth) ---
    # Load current stocks from Master data (Persistent state)
    # This list reflects the state AT THE START of the run.
    p_type = "Unified"
    if selected_portfolio:
        p_rows = user_all_data[user_all_data['portfolio_name'] == selected_portfolio]
        if not p_rows.empty:
            p_type = p_rows['portfolio_type'].iloc[0]

    user_portfolio_df = user_all_data[user_all_data['portfolio_name'] == selected_portfolio] if selected_portfolio else pd.DataFrame()
    user_portfolio_df = user_portfolio_df[user_portfolio_df['stock_name'] != "__PLACEHOLDER__"] if not user_portfolio_df.empty else pd.DataFrame()
    
    # 2. Main Page Header & State Management Logic (Sync with DB) for consistent UI
    if not user_portfolio_df.empty:
        user_portfolio_df = user_portfolio_df.sort_values(by='target_allocation', ascending=False)
    
    # Initialize session state for stocks ONLY if portfolio changes or it's first run
    if st.session_state.get('last_selected_portfolio') != selected_portfolio:
        current_stocks = []
        if p_type == "Unified":
            # Map tickers and aggregate duplicate holdings (e.g. from historical merges)
            ticker_map = {
                "WTEQ.DE": "WTEQ.DE",
                "VDIV.DE": "VDIV.DE",
                "JMT.PT": "JMT.PT",
                "EDP.PT": "EDP.PT",
                "EGNL.UK": "EGLN.UK",
                "EGLN.UK": "EGLN.UK",
                "IBTE.UK": "PRAB.DE"
            }
            aggregated_holdings = {}
            for _, row in user_portfolio_df.iterrows():
                raw_name = str(row['stock_name'])
                mapped_name = ticker_map.get(raw_name, raw_name)
                
                if mapped_name not in aggregated_holdings:
                    aggregated_holdings[mapped_name] = {
                        "name": mapped_name,
                        "current_value": 0.0,
                        "target_allocation": 0.0,
                        "tolerance": TOLERANCE_PP.get(mapped_name, 2.0),
                        "expense_ratio": float(row.get('expense_ratio', 0.0)),
                        "full_name": row.get('stock_full_name', mapped_name),
                        "sector": row.get('sector', ''),
                        "industry": row.get('industry', ''),
                        "country": row.get('country', ''),
                        "currency": row.get('currency', 'EUR'),
                        "quantity": 0.0,
                        "average_price": float(row.get('average_price', 0.0)),
                        "current_price": float(row.get('current_price', 0.0)),
                        "dividend_yield": float(row.get('dividend_yield', 0.0))
                    }
                
                rec = aggregated_holdings[mapped_name]
                rec["current_value"] += float(row['current_value'])
                rec["quantity"] += float(row.get('quantity', 0.0))
                if rec["expense_ratio"] == 0.0 and float(row.get('expense_ratio', 0.0)) > 0.0:
                    rec["expense_ratio"] = float(row.get('expense_ratio', 0.0))
                if rec["current_price"] == 0.0 and float(row.get('current_price', 0.0)) > 0.0:
                    rec["current_price"] = float(row.get('current_price', 0.0))

            current_stocks = list(aggregated_holdings.values())
            
            # Ensure all 9 target assets are present in the list
            required_tickers = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "WTEQ.DE", "VDIV.DE", "JMT.PT", "EDP.PT", "EGLN.UK", "PRAB.DE"]
            existing_tickers = [s["name"] for s in current_stocks]
            for ticker in required_tickers:
                if ticker not in existing_tickers:
                    current_stocks.append({
                        "name": ticker,
                        "current_value": 0.0,
                        "target_allocation": 0.0,
                        "tolerance": TOLERANCE_PP.get(ticker, 2.0),
                        "expense_ratio": 0.0,
                        "full_name": ticker,
                        "sector": "",
                        "industry": "",
                        "country": "",
                        "currency": "EUR",
                        "quantity": 0.0,
                        "average_price": 0.0,
                        "current_price": 0.0,
                        "dividend_yield": 0.0
                    })
        else:
            for _, row in user_portfolio_df.iterrows():
                current_stocks.append({
                    "name": row['stock_name'],
                    "current_value": row['current_value'],
                    "target_allocation": row['target_allocation'],
                    "tolerance": row.get('tolerance', 0.0),
                    "expense_ratio": row.get('expense_ratio', 0.0),
                    "full_name": row.get('stock_full_name', ''),
                    "sector": row.get('sector', ''),
                    "industry": row.get('industry', ''),
                    "country": row.get('country', ''),
                    "currency": row.get('currency', ''),
                    "quantity": float(row.get('quantity', 0.0)),
                    "average_price": float(row.get('average_price', 0.0)),
                    "current_price": float(row.get('current_price', 0.0)),
                    "dividend_yield": float(row.get('dividend_yield', 0.0))
                })
        st.session_state.stocks = current_stocks
        st.session_state.last_selected_portfolio = selected_portfolio

        # Pre-populate session state keys for widgets if they don't exist
        if selected_portfolio:
            # Load portfolio-level config from the first row of user_portfolio_df
            if not user_portfolio_df.empty:
                first_row = user_portfolio_df.iloc[0]
                # Note: We use fixed keys for portfolio-level settings
                st.session_state[f"{selected_portfolio}_monthly_invest"] = float(first_row.get('portfolio_monthly_invest', 1000.0))
                st.session_state[f"{selected_portfolio}_use_indicators"] = bool(first_row.get('portfolio_use_indicators', False))
                st.session_state[f"{selected_portfolio}_buffett_index"] = float(first_row.get('portfolio_buffett_index', 195.0))
                st.session_state[f"{selected_portfolio}_birth_date"] = first_row.get('portfolio_birth_date', '')
                try:
                    st.session_state[f"{selected_portfolio}_uninvested_cash"] = float(first_row.get('portfolio_uninvested_cash', 0.0))
                except (ValueError, TypeError):
                    st.session_state[f"{selected_portfolio}_uninvested_cash"] = 0.0
                
                st.session_state[f"{selected_portfolio}_investor_birth_date"] = first_row.get('investor_birth_date', '1992-01-01')
                
            for idx, stock in enumerate(st.session_state.stocks):
                key_prefix = f"{selected_portfolio}_{idx}"
                st.session_state[f"{key_prefix}_name"] = stock['name']
                st.session_state[f"{key_prefix}_value"] = float(stock['current_value'])
                st.session_state[f"{key_prefix}_target"] = float(stock['target_allocation'])
                st.session_state[f"{key_prefix}_tolerance"] = float(stock.get('tolerance', 0.0))

    # --- Dynamic Overrides (Run every rerun to catch Birth Date changes) ---
    if selected_portfolio and 'stocks' in st.session_state:
        # 1. Kids Targets
        if p_type == "Kids" and st.session_state.get(f"{selected_portfolio}_birth_date"):
            kids_targets = calculate_kids_targets(st.session_state[f"{selected_portfolio}_birth_date"])
            if kids_targets:
                for ticker, target in kids_targets.items():
                    for stock in st.session_state.stocks:
                        if stock['name'] == ticker:
                            stock['target_allocation'] = target
                            break

        # 3. Unified Targets and Tolerances Overrides
        if p_type == "Unified":
            birth_date_str = st.session_state.get(f"{selected_portfolio}_investor_birth_date", "1992-01-01")
            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                today = date.today()
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            except Exception:
                age = 34
            
            buffett_index = float(st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0))
            
            try:
                targets_data = calculate_portfolio_targets(age, buffett_index)
                unified_targets = targets_data["targets"]
            except Exception as e:
                st.error(f"Error calculating Unified Targets: {e}")
                unified_targets = {}
            
            for stock in st.session_state.stocks:
                ticker = stock['name']
                if ticker in unified_targets:
                    stock['target_allocation'] = unified_targets[ticker]
                    stock['tolerance'] = TOLERANCE_PP.get(ticker, 2.0)
                else:
                    stock['target_allocation'] = 0.0
                    stock['tolerance'] = 2.0

    # Sidebar utilities (Configuration and Indicators)
    with st.sidebar:
        if selected_portfolio:
            # 2. Configuration Section
            if p_type in ["Kids", "Unified"]:
                # Default expander behavior: auto-expand for 'Kids' to set birth date, others remain collapsed
                with st.expander("⚙️ Configuration", expanded=(p_type == "Kids")):
                    if p_type == "Unified":
                        investor_birth_key = f"{selected_portfolio}_investor_birth_date"
                        current_investor_birth = st.session_state.get(investor_birth_key, '1992-01-01')
                        
                        try:
                            if isinstance(current_investor_birth, str) and current_investor_birth:
                                default_date = datetime.strptime(current_investor_birth, "%Y-%m-%d").date()
                            else:
                                default_date = date(1992, 1, 1)
                        except ValueError:
                            default_date = date(1992, 1, 1)
                            
                        investor_birth_input = st.date_input(
                            "Investor's Birth Date",
                            value=default_date,
                            min_value=date(1900, 1, 1),
                            max_value=datetime.today().date(),
                            key=f"{investor_birth_key}_input",
                            on_change=clear_recommendations
                        )
                        
                        if str(investor_birth_input) != current_investor_birth:
                            st.session_state[investor_birth_key] = str(investor_birth_input)
                            st.session_state.has_unsaved_changes = True
                            st.rerun()

                    if p_type == "Kids":
                        birth_date_key = f"{selected_portfolio}_birth_date"
                        current_birth_date = st.session_state.get(birth_date_key, '')
                        
                        try:
                            # Robust check for string type to avoid numpy.float64 (NaN) crashes
                            if isinstance(current_birth_date, str) and current_birth_date:
                                default_date = datetime.strptime(current_birth_date, "%Y-%m-%d").date()
                            else:
                                default_date = datetime.today().date()
                        except ValueError:
                            default_date = datetime.today().date()
                            
                        birth_date_input = st.date_input(
                            "Child's Birth Date",
                            value=default_date,
                            min_value=datetime(1900, 1, 1).date(),
                            max_value=datetime(2100, 1, 1).date(),
                            key=f"{birth_date_key}_input",
                            on_change=clear_recommendations
                        )
                        
                        if str(birth_date_input) != current_birth_date:
                            st.session_state[birth_date_key] = str(birth_date_input)
                            st.session_state.has_unsaved_changes = True
                            
                            # Auto-calculate age-based targets
                            kids_targets = calculate_kids_targets(str(birth_date_input))
                            if kids_targets:
                                existing_tickers = {s['name'] for s in st.session_state.stocks}
                                for ticker, target in kids_targets.items():
                                    if ticker in existing_tickers:
                                        for i, stock in enumerate(st.session_state.stocks):
                                            if stock['name'] == ticker:
                                                st.session_state.stocks[i]['target_allocation'] = target
                                                st.session_state[f"{selected_portfolio}_{i}_target"] = target
                                                break
                                    elif ticker in ["VWCE.DE", "VAGF.DE"]:
                                        # Auto-inject core tickers if they don't exist in the portfolio yet
                                        st.session_state.stocks.append({
                                            "name": ticker,
                                            "current_value": 0.0,
                                            "target_allocation": target,
                                            "tolerance": 2.0,
                                            "expense_ratio": 0.0,
                                            "full_name": ticker,
                                            "sector": "", "industry": "", "country": "", "currency": "EUR", "quantity": 0.0, "average_price": 0.0, "dividend_yield": 0.0
                                        })
                                st.toast("👶 Age-based targets updated!", icon="✅")
                                st.rerun()


                    # Calculate Previous Month's Dividends (for Dividends Portfolios)
                    prev_month_divs = 0.0
                    now = datetime.now()
                    if now.month == 1:
                        prev_month, prev_year = 12, now.year - 1
                    else:
                        prev_month, prev_year = now.month - 1, now.year
                    
                    prev_month_name = date(prev_year, prev_month, 1).strftime('%B')

                    if p_type == "Unified":
                        div_df = st.session_state.dividends
                        if not div_df.empty:
                            div_df['date'] = pd.to_datetime(div_df['date'], errors='coerce')
                            div_df['amount'] = pd.to_numeric(div_df['amount'], errors='coerce').fillna(0.0)
                            
                            mask = (div_df['username'] == username) & \
                                   (div_df['portfolio_name'] == selected_portfolio) & \
                                   (div_df['date'].dt.month == prev_month) & \
                                   (div_df['date'].dt.year == prev_year)
                            
                            prev_month_divs = div_df[mask]['amount'].sum()

                    current_month = datetime.now().month
                    if p_type == "Kids":
                        base_investment = 100.0 if current_month in [6, 12] else 50.0
                    elif p_type == "Unified":
                        base_investment = 1000.0 if current_month in [6, 12] else 500.0
                    else:
                        base_investment = 500.0 # Default fallback
                        
                    st.markdown(f"**💳 Base Investment:** €{base_investment:,.2f}")

                    if p_type == "Unified":
                        monthly_investment = base_investment + prev_month_divs
                        
                        # Show Breakdown in Sidebar
                        st.markdown(f"**📅 Dividends ({prev_month_name}):** €{prev_month_divs:,.2f}")
                        st.markdown(f"**💰 Total Monthly Investment:** :green[€{monthly_investment:,.2f}]")
                    else:
                        monthly_investment = base_investment
                    
                    if p_type == "Unified":
                        st.markdown("### Market Indicators")
                        buffett_index_key = f"{selected_portfolio}_buffett_index"
                        buffett_index = st.number_input(
                            "Buffett Indicator (%)", 
                            key=buffett_index_key,
                            value=st.session_state.get(buffett_index_key, 195.0),
                            step=0.1, 
                            help="Market Cap to GDP ratio",
                            on_change=clear_recommendations
                        )
                        growth_split = calculate_growth_split(buffett_index)
                        st.info(f"Growth Split 🎯 | SPYL: {growth_split['SPYL.DE']:.1f}%, IXUA: {growth_split['IXUA.DE']:.1f}%, VFEA: {growth_split['VFEA.DE']:.1f}%")


            else:
                # Still need defaults for variables used later even if hidden
                monthly_investment = 0.0
                use_market_indicators = False
                buffett_index = 195.0
            

        else:
            monthly_investment = 1000.0 # Default fallback for later logic



    # Main content
    if selected_portfolio == "🌍 Global Overview":
        st.markdown("## 🌍 Global Portfolio Overview")
        st.divider()
        if not merged_global.empty:
            fig_global = px.pie(merged_global, values='total_value', names='portfolio_name', hole=0.75, color_discrete_sequence=CHART_PALETTE)
            fig_global.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=60, b=60, l=40, r=40),
                showlegend=False,
                height=500
            )
            fig_global.update_traces(
                textposition='outside',
                texttemplate="<b>%{label}</b><br>%{value:,.2f} € | %{percent}", 
                textfont=dict(size=15),
                hovertemplate="<b>%{label}</b><br>Value: €%{value:,.2f}<br>Weight: %{percent}<extra></extra>",
                marker=dict(line=dict(color='rgba(0,0,0,0)', width=0))
            )
            st.plotly_chart(fig_global, use_container_width=True)
        else:
            st.info("No value invested yet or no data available.")
    elif selected_portfolio:
        # Synchronize "live" values for calculations (Summary/Recommendations) 
        # Source of truth is now exclusively st.session_state.stocks (synced with Editor)
        import copy
        live_stocks = copy.deepcopy(st.session_state.stocks) if 'stocks' in st.session_state else []
        
        # Custom sort order: PRAB and EGLN placed immediately after VFEA.DE
        custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "PRAB.DE", "EGLN.UK"]
        live_stocks.sort(key=lambda x: custom_order_list.index(x.get('name', '')) if x.get('name', '') in custom_order_list else 99)

        # --- Top Row: KPI Cards ---
        total_current = sum(s['current_value'] for s in live_stocks)
        total_target = sum(s['target_allocation'] for s in live_stocks)
        num_stocks = len(live_stocks)
        
        # Dashboard Header
        formatted_title = format_portfolio_name(selected_portfolio) if "format_portfolio_name" in locals() else f"📊 {selected_portfolio}"
        st.markdown(f"## {formatted_title} Dashboard")
        
        # Calculate Current Weighted TER for KPI (including all assets in THIS selected portfolio)
        total_ter_sum = 0.0
        portfolio_total_all_assets = sum(float(s.get('current_value', 0.0)) for s in live_stocks)
        
        for s in live_stocks:
            try:
                current_val = float(s.get('current_value', 0.0))
                ter = float(s.get('expense_ratio', 0.0))
                total_ter_sum += (current_val * ter)
            except (ValueError, TypeError):
                continue
                
        weighted_ter = (total_ter_sum / portfolio_total_all_assets) if portfolio_total_all_assets > 0 else 0.0

        if p_type == "Stocks":
            # Calculate Unique Sectors
            unique_sectors = set(s.get('sector', '') for s in live_stocks if s.get('sector', ''))
            num_sectors = len(unique_sectors)
            # Calculate total volume (sum of all quantities)
            total_volume = sum(float(s.get('quantity', 0.0) or 0.0) for s in live_stocks)
            # Total Invested Value
            total_invested = sum(float(s.get('current_price', 0.0) or 0.0) for s in live_stocks)
            # Profit / Loss
            profit = total_current - total_invested
            profit_pct = (profit / total_invested * 100.0) if total_invested > 0 else 0.0
            profit_prefix = "+" if profit >= 0 else ""
            profit_class = "profit-green" if profit >= 0 else "profit-red"

            # Weighted Dividend Yield (Market Value weighted)
            total_market_val = sum(float(s.get('current_value', 0.0) or 0.0) for s in live_stocks)
            weighted_div_yield_sum = sum(float(s.get('current_value', 0.0) or 0.0) * float(s.get('dividend_yield', 0.0) or 0.0) for s in live_stocks)
            portfolio_div_yield = (weighted_div_yield_sum / total_market_val) if total_market_val > 0 else 0.0

            # Weighted Yield on Cost (Invested Value weighted)
            portfolio_yoc = (weighted_div_yield_sum / total_invested) if total_invested > 0 else 0.0

            # Render in two beautifully structured rows (3 columns per row)
            # Row 1: Financial Performance & Volumes
            kpi_row1 = st.columns(3)
            with kpi_row1[0]: 
                render_kpi_card("Total Market Value", f"€{total_current:,.2f}")
            with kpi_row1[1]: 
                render_kpi_card("Profit", f'<span class="{profit_class}">€{profit_prefix}{profit:,.2f} ({profit_prefix}{profit_pct:+.2f}%)</span>')
            with kpi_row1[2]: 
                render_kpi_card("Volumes Count", f"{total_volume:,.0f}")

            # Row 2: Portfolio Characteristics & Yields
            kpi_row2 = st.columns(3)
            with kpi_row2[0]: 
                render_kpi_card("Stocks by Sectors", f"{num_stocks} / {num_sectors}")
            with kpi_row2[1]: 
                render_kpi_card("Dividend Yield", f"{portfolio_div_yield:.2f}%")
            with kpi_row2[2]: 
                render_kpi_card("Yield on Cost", f"{portfolio_yoc:.2f}%")
        else:
            kpi_cols = st.columns(4)
            count_label = "ETFs Count" if p_type == "Kids" else "Stocks / ETFs Count"
            with kpi_cols[0]: render_kpi_card("Total Value", f"€{total_current:,.2f}")
            with kpi_cols[1]: render_kpi_card(count_label, f"{num_stocks}")
            with kpi_cols[2]: render_kpi_card("Weighted TER", f"{weighted_ter:.2f}%")
            with kpi_cols[3]: render_kpi_card("Monthly Budget", f"€{monthly_investment:,.2f}")
        
        if p_type != "Stocks" and abs(total_target - 100.0) > 0.01:
            st.warning("⚠️ Your target allocations do not sum to 100%. Please adjust them in Portfolio Management.")

        # --- Tab Routing Logic ---
        
        tab_list = []
        if p_type == "Stocks":
            tab_list = ["📈 Portfolio Details", "💰 Dividend Tracker", "🪙 Uninvested Cash"]
        elif p_type == "Unified":
            tab_list = ["📊 Manage Portfolio", "💰 Dividend Tracker", "🪙 Uninvested Cash"]
        else: # Kids
            tab_list = ["📊 Manage Portfolio", "🪙 Uninvested Cash"]
            
        if selected_portfolio and "conviction" in selected_portfolio.lower():
            if "🪙 Uninvested Cash" in tab_list:
                tab_list.remove("🪙 Uninvested Cash")

            
        tabs = st.tabs(tab_list)
        
        # Link tab objects to labels for easier conditional rendering
        tab_map = {label: tabs[i] for i, label in enumerate(tab_list)}

        if "📊 Manage Portfolio" in tab_map:
            with tab_map["📊 Manage Portfolio"]:
                st.session_state.footer_msg = "<b>Smart Rebalancing:</b> Maintain your risk profile with disciplined allocation."
                uninvested_cash = float(st.session_state.get(f"{selected_portfolio}_uninvested_cash", 0.0))
                if uninvested_cash > 0:
                    st.info(f"💡 You have **€{uninvested_cash:,.2f}** of uninvested cash. You can manage it in the 'Uninvested Cash' tab.", icon="🪙")
                    
                col_main, col_side = st.columns([2, 1])
        
                with col_main:
                    with st.container(border=True):
                        st.subheader("📝 Portfolio Management")
                        
                        # Prepare data for Editor
                        current_stocks_df = pd.DataFrame(st.session_state.stocks)
                        if not current_stocks_df.empty:
                            # Slice to only include core rebalancing columns for this tab
                            # Keep 'name' as a column to style the ticker too
                            core_cols = ["name", "current_value", "target_allocation", "tolerance", "expense_ratio"]
                            
                            available_core = [c for c in core_cols if c in current_stocks_df.columns]
                            current_stocks_df = current_stocks_df[available_core]



                            # Custom order logic
                            custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "PRAB.DE", "EGLN.UK"]
                            current_stocks_df['order_idx'] = current_stocks_df['name'].apply(lambda x: custom_order_list.index(x) if x in custom_order_list else 99)
                            current_stocks_df = current_stocks_df.sort_values(by='order_idx').drop(columns=['order_idx']).reset_index(drop=True)
                            current_stocks_df.set_index("name", inplace=True)
                        else:
                            current_stocks_df = pd.DataFrame(columns=["name", "current_value", "target_allocation", "tolerance", "expense_ratio", "current_price"])
                            current_stocks_df.set_index("name", inplace=True)
                        
                        # Configuration for Data Editor
                        column_config = {
                            "_index": st.column_config.TextColumn("Ticker", required=True, disabled=True),
                            "current_value": st.column_config.NumberColumn("Value (€)", min_value=0.0, step=0.01, format="%.2f"),
                            "target_allocation": st.column_config.NumberColumn(
                                "Target %", min_value=0.0, max_value=100.0, step=0.01, format="%.2f%%", 
                                disabled=(p_type in ["Kids", "Unified"])
                            ),
                            "current_price": st.column_config.NumberColumn("Price (€)", min_value=0.0, step=0.01, format="%.2f"),
                            "tolerance": st.column_config.NumberColumn(
                                "Tolerance %", min_value=0.0, max_value=20.0, step=0.1, format="%.1f%%",
                                disabled=(p_type in ["Unified"])
                            ),
                            "expense_ratio": st.column_config.NumberColumn("TER %", min_value=0.0, max_value=5.0, step=0.01, format="%.2f%%")
                        }
                        
                        edited_df = st.data_editor(
                            current_stocks_df,
                            column_config=column_config,
                            num_rows="dynamic",
                            use_container_width=True,
                            key=f"portfolio_editor_{st.session_state.editor_key}",
                            on_change=clear_recommendations
                        )
                        
                        # Sync Editor Changes to Session State immediately for "Live Calc"
                        # This ensures charts and calculations use the latest typed values even before saving
                        if not edited_df.equals(current_stocks_df):
                            # DETECT DELETIONS
                            updated_stocks = edited_df.reset_index().to_dict('records')
                            old_stocks = current_stocks_df.reset_index().to_dict('records')
        
                            if len(updated_stocks) < len(old_stocks):
                                # Row(s) were deleted
                                # Identify exactly which ones are missing based on 'name' (assuming unique names)
                                updated_names = {row['name'] for row in updated_stocks}
                                deleted_items = [row for row in old_stocks if row['name'] not in updated_names]
                                
                                st.session_state.undo_buffer = deleted_items
                                st.session_state.show_undo = True
                                st.toast(f"Deleted {len(deleted_items)} stock(s)", icon="🗑️")
                            elif len(updated_stocks) >= len(old_stocks):
                                # Add or Edit action -> Clear undo history to avoid confusion
                                st.session_state.show_undo = False
                                st.session_state.undo_buffer = []
        
                            st.session_state.has_unsaved_changes = True
                            
                            # ROBUST SYNC: Merge changes without wiping metadata
                            current_stocks_map = {s['name']: s for s in st.session_state.stocks}
                            updated_list = []
                            
                            for updated_row in updated_stocks:
                                ticker = updated_row['name']
                                if ticker in current_stocks_map:
                                    # Merge updated values from editor into full original record
                                    merged = current_stocks_map[ticker].copy()
                                    merged.update(updated_row)
                                    updated_list.append(merged)
                                else:
                                    # Brand new row
                                    updated_list.append(updated_row)
                            
                            st.session_state.stocks = updated_list
                            
                            # Aggressive sync: Rerun ensures Dashboard KPIs and other blocks see the new state immediately
                            st.rerun()
        
                        # UNDO BUTTON
                        if st.session_state.show_undo:
                            if st.button("↩️ Undo Delete"):
                                if st.session_state.undo_buffer:
                                    # Restore deleted items
                                    st.session_state.stocks.extend(st.session_state.undo_buffer)
                                    st.session_state.undo_buffer = []
                                    st.session_state.show_undo = False
                                    
                                    # CRITICAL FIX (Robust): Increment key to force total widget recreation
                                    # This bypasses any internal state that Streamlit/BaseWeb might be holding onto
                                    st.session_state.editor_key += 1
                                        
                                    st.toast("Restored deleted stocks!", icon="✅")
                                    st.rerun()
        
        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Save Logic
                        if st.button("💾 Save All Changes", width="stretch"):
                            any_content_changes = False
                            
                            # 1. Update Portfolio-Level Config (Broadcast)
                            portfolio_invest = st.session_state.get(f"{selected_portfolio}_monthly_invest", 1000.0)
                            portfolio_use_ind = st.session_state.get(f"{selected_portfolio}_use_indicators", False)
                            portfolio_buffett = st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0)
                            portfolio_birth_date = st.session_state.get(f"{selected_portfolio}_birth_date", "")
                            try:
                                portfolio_uninvested_cash = float(st.session_state.get(f"{selected_portfolio}_uninvested_cash", 0.0))
                            except:
                                portfolio_uninvested_cash = 0.0
                            portfolio_type = p_type
                            portfolio_investor_birth = st.session_state.get(f"{selected_portfolio}_investor_birth_date", '1992-01-01')
        
                            mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                            
                            # Check for Config Changes
                            if not user_portfolio_df.empty:
                                fr = user_portfolio_df.iloc[0]
                                try:
                                    fr_cash = float(fr.get('portfolio_uninvested_cash', 0.0))
                                except:
                                    fr_cash = 0.0
                                if (abs(portfolio_invest - fr.get('portfolio_monthly_invest', 1000.0)) > 0.1 or
                                    portfolio_use_ind != fr.get('portfolio_use_indicators', False) or
                                    portfolio_birth_date != fr.get('portfolio_birth_date', '') or
                                    abs(portfolio_uninvested_cash - fr_cash) > 0.01 or
                                    portfolio_investor_birth != fr.get('investor_birth_date', '1992-01-01') or
                                    abs(portfolio_buffett - fr.get('portfolio_buffett_index', 195.0)) > 0.1):
                                    any_content_changes = True
                                    data.loc[mask, 'portfolio_monthly_invest'] = portfolio_invest
                                    data.loc[mask, 'portfolio_use_indicators'] = portfolio_use_ind
                                    data.loc[mask, 'portfolio_buffett_index'] = portfolio_buffett
                                    data.loc[mask, 'portfolio_birth_date'] = portfolio_birth_date
                                    data.loc[mask, 'portfolio_uninvested_cash'] = portfolio_uninvested_cash
                                    data.loc[mask, 'investor_birth_date'] = portfolio_investor_birth
                            
                            # 2. Update Stock Data (Refactored for Data Editor)
                            # We rebuild the rows for this portfolio entirely from the edited_df
                            # This handles Adds, Edits, and Deletes implicitly
                            
                            # First, drop all existing rows for this portfolio
                            data = data[~mask]
                            
                            # Then create new rows from edited_df
                            new_rows = []
                            for _, row in edited_df.reset_index().iterrows():
                                if row['name'] and row['name'] != "__PLACEHOLDER__":
                                     new_rows.append({
                                        "username": username,
                                        "portfolio_name": selected_portfolio,
                                        "stock_name": row['name'],
                                        "current_value": row['current_value'],
                                        "target_allocation": row['target_allocation'],
                                        "current_price": row.get('current_price', 0.0),
                                        "tolerance": row['tolerance'],
                                        "expense_ratio": row.get('expense_ratio', 0.0),
                                        "portfolio_monthly_invest": portfolio_invest,
                                        "portfolio_use_indicators": portfolio_use_ind,
                                        "portfolio_buffett_index": portfolio_buffett,
                                        "portfolio_birth_date": portfolio_birth_date,
                                        "portfolio_uninvested_cash": portfolio_uninvested_cash,
                                        "investor_birth_date": portfolio_investor_birth,
                                        "portfolio_type": portfolio_type,
                                        "stock_full_name": row.get('full_name', ''),
                                        "sector": row.get('sector', ''),
                                        "industry": row.get('industry', ''),
                                        "country": row.get('country', ''),
                                        "currency": row.get('currency', ''),
                                        "quantity": float(row.get('quantity', 0.0)),
                                        "average_price": float(row.get('average_price', 0.0)),
                                        "dividend_yield": float(row.get('dividend_yield', 0.0))
                                    })
                            
                            if not new_rows:
                                # If empty, add placeholder to keep portfolio alive
                                 new_rows.append({
                                    "username": username,
                                    "portfolio_name": selected_portfolio,
                                    "stock_name": "__PLACEHOLDER__",
                                    "current_value": 0.0,
                                    "target_allocation": 0.0,
                                     "portfolio_monthly_invest": portfolio_invest,
                                    "portfolio_use_indicators": portfolio_use_ind,
                                    "portfolio_buffett_index": portfolio_buffett,
                                    "portfolio_type": portfolio_type,
                                    "stock_full_name": '',
                                    "sector": '',
                                    "industry": '',
                                    "country": '',
                                    "currency": '',
                                    "quantity": 0.0,
                                    "average_price": 0.0,
                                    "dividend_yield": 0.0
                                })
                            
                            updated_data = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
                            st.session_state.master_data = updated_data
                            conn.update(worksheet="Portfolios", data=updated_data)
                            
                            st.session_state.has_unsaved_changes = False
                            st.session_state.show_save_success = True
                            st.rerun()
                            
                        if st.session_state.get('show_save_success'):
                            st.success("All changes saved successfully!")
                            st.session_state.show_save_success = False
                with col_side:
                    with st.container(border=True):
                        st.subheader("🎯 Action Center")
                        if st.button("🧮 Calculate Allocation", width="stretch"):
                            if p_type == "Unified":
                                import copy
                                live_stocks = copy.deepcopy(st.session_state.stocks)
                                current_monthly_base = float(monthly_investment)
                                
                                # Prepare current values
                                current_values = {s['name']: s['current_value'] for s in live_stocks}
                                
                                # Extract investor's age
                                birth_date_str = st.session_state.get(f"{selected_portfolio}_investor_birth_date", "1992-01-01")
                                try:
                                    birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                                    today = date.today()
                                    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                                except Exception:
                                    age = 34
                                    
                                # Extract Buffett Index
                                buffett_index = float(st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0))
                                
                                # Execute monthly buys logic with defensive transition plan
                                try:
                                    # Get dynamic target weights for EGLN.UK and PRAB.DE
                                    targets_data = calculate_portfolio_targets(age, buffett_index)
                                    targets = targets_data["targets"]
                                    egln_tgt = targets.get("EGLN.UK", 3.0)
                                    prab_tgt = targets.get("PRAB.DE", 2.7)
                                    
                                    total_port_val = sum(current_values.get(asset, 0.0) for asset in current_values)
                                    
                                    transition_plan = calculate_egln_prab_transition_plan(
                                        portfolio_value=total_port_val,
                                        monthly_contribution=current_monthly_base,
                                        current_egln_value=current_values.get("EGLN.UK", 0.0),
                                        current_prab_value=current_values.get("PRAB.DE", 0.0),
                                        months=4,
                                        egln_target_pct=egln_tgt,
                                        prab_target_pct=prab_tgt,
                                        min_order_size=5.0
                                    )
                                    
                                    # Extract first month's purchases
                                    current_month_plan = transition_plan[0]
                                    egln_buy = current_month_plan["egln_buy"]
                                    prab_buy = current_month_plan["prab_buy"]
                                    remaining_contrib = current_month_plan["remaining_for_normal_strategy"]
                                    
                                    # Allocate the rest of the monthly contribution using normal rebalancing on remaining assets
                                    buys_data = calculate_monthly_buys(
                                        age=age,
                                        buffett_index=buffett_index,
                                        current_values=current_values,
                                        monthly_contribution=remaining_contrib,
                                        min_order_size=5.0,
                                        exclude_defensive=True
                                    )
                                    
                                    # Integrate transition buys back into the final results
                                    buys_data["buys"]["EGLN.UK"] = egln_buy
                                    buys_data["buys"]["PRAB.DE"] = prab_buy
                                    
                                    buys_data["raw_buys"]["EGLN.UK"] = egln_buy
                                    buys_data["raw_buys"]["PRAB.DE"] = prab_buy
                                    
                                    buys_data["portfolio_value_after"] = round(total_port_val + current_monthly_base, 2)
                                    buys_data["portfolio_targets"] = targets
                                    
                                except Exception as e:
                                    st.error(f"Error calculating Unified buys: {e}")
                                    st.stop()
                                    
                                portfolio_targets = buys_data["portfolio_targets"]
                                current_weights = buys_data["current_weights"]
                                buys_map = buys_data["buys"]
                                leftover_cash = buys_data["leftover_cash"]
                                
                                portfolio_value_before = buys_data["portfolio_value_before"]
                                portfolio_value_after = buys_data["portfolio_value_after"]
                                
                                allocations = []
                                for stock in live_stocks:
                                    ticker = stock['name']
                                    final_invest = buys_map.get(ticker, 0.0)
                                    target_pct = portfolio_targets.get(ticker, 0.0)
                                    target_val = portfolio_value_after * (target_pct / 100.0)
                                    new_val = stock['current_value'] + final_invest
                                    
                                    allocations.append({
                                        "Stock": ticker,
                                        "Current Value": stock['current_value'],
                                        "Current %": current_weights.get(ticker, 0.0),
                                        "TER %": stock.get('expense_ratio', 0.0),
                                        "Target %": target_pct,
                                        "Target Value": target_val,
                                        "Investment": final_invest,
                                        "New Value": new_val,
                                        "New %": (new_val / portfolio_value_after * 100) if portfolio_value_after > 0 else 0
                                    })
                                
                                invest_map = buys_map
                                total_current_live = portfolio_value_before
                                current_monthly_base = current_monthly_base
                                remaining_investment = leftover_cash
                                
                                if 'vault_alloc_by_portfolio' not in st.session_state:
                                    st.session_state.vault_alloc_by_portfolio = {}
                                st.session_state.vault_alloc_by_portfolio[selected_portfolio] = {
                                    "type": p_type,
                                    "EGLN.UK": buys_map.get("EGLN.UK", 0.0),
                                    "PRAB.DE": buys_map.get("PRAB.DE", 0.0),
                                }
                                
                                import pandas as pd
                                alloc_df = pd.DataFrame(allocations)
                                if not alloc_df.empty:
                                    custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "PRAB.DE", "EGLN.UK"]
                                    alloc_df['order_idx'] = alloc_df['Stock'].apply(lambda x: custom_order_list.index(x) if x in custom_order_list else 99)
                                    alloc_df = alloc_df.sort_values(by='order_idx').drop(columns=['order_idx'])
                                    
                                st.session_state.last_calculation = {
                                    "df": alloc_df,
                                    "monthly_investment": current_monthly_base,
                                    "remaining": remaining_investment
                                }
                                st.session_state.show_recommendations = True
                            else:
                                import copy
                                live_stocks = copy.deepcopy(st.session_state.stocks)
                                
                                total_current_global = sum(s['current_value'] for s in live_stocks)
                                core_target_live = sum(s['target_allocation'] for s in live_stocks)
            
                                # The Core stocks must strictly sum to 100%
                                if abs(core_target_live - 100.0) > 0.01:
                                    st.error(f"As suas ações base somam {core_target_live:.1f}%. Ajuste para que somem exatamente 100%.")
                                else:
                                    import math
                                    
                                    # Current local Monthly Investment (from Sidebar or Auto)
                                    current_monthly_base = float(monthly_investment) 
                                    
                                    global_theoretical = total_current_global + current_monthly_base
                                    remaining_investment = float(current_monthly_base)
                                    
                                    # Initial map for all stocks
                                    final_investments = {s['name']: 0.0 for s in live_stocks}
                                    stocks_to_process = [s for s in live_stocks]
                                    

                                    # Formally set Rebased Totals so Core targets (which sum to 100%) distribute flawlessly
                                    total_current_live = sum(s['current_value'] for s in stocks_to_process)
                                    total_theoretical = total_current_live + remaining_investment
                                    
                                    # --- STEP 1: Special Handling for RENE.PT...
                                    if selected_portfolio and "dividends" in selected_portfolio.lower():
                                        rene_stock = next((s for s in live_stocks if s['name'].upper() == "RENE.PT"), None)
                                        if rene_stock:
                                            target_val = total_theoretical * (rene_stock['target_allocation'] / 100.0)
                                            gap = target_val - rene_stock['current_value']
                                            price = rene_stock.get('current_price', 0.0)
                                            
                                            invest_real = 0.0
                                            if gap > 0 and price > 0:
                                                # Determine integer quantity based on Gap
                                                qty = math.floor(gap / price)
                                                invest_real = qty * price
                                                
                                                # Cap by available monthly investment
                                                if invest_real > remaining_investment:
                                                    qty = math.floor(remaining_investment / price)
                                                    invest_real = qty * price
                                                
                                                # MinBuy check (5€)
                                                if invest_real < 5.0 and invest_real > 0:
                                                    invest_real = 0.0
                                            
                                            final_investments[rene_stock['name']] = invest_real
                                            remaining_investment -= invest_real
                                            # Remove RENE from the common pool for the next phases
                                            stocks_to_process = [s for s in stocks_to_process if s['name'].upper() != "RENE.PT"]
     
                                    # --- STEP 2: Standard Rebalancing Algorithm for Remaining Stocks ---
                                    if remaining_investment > 0 and stocks_to_process:
                                        # Phase A: Calculate Gaps and identify deviations
                                        stock_data_p = []
                                        sum_positive_deviations = 0.0
                                        
                                        for stock in stocks_to_process:
                                            current_weight = (stock['current_value'] / total_current_live * 100.0) if total_current_live > 0 else 0.0
                                            target_weight = stock['target_allocation']
                                            deviation = target_weight - current_weight
                                            
                                            min_band = target_weight - stock.get('tolerance', 0.0)
                                            below_min_band = current_weight < min_band
                                            below_target = deviation > 0
                                            
                                            if below_target:
                                                # Note: We don't cap by max_band here as requested for Dividends redistribution logic
                                                sum_positive_deviations += deviation
                                                
                                            target_val = total_theoretical * (target_weight / 100.0)
                                            gap = target_val - stock['current_value']
                                            
                                            stock_data_p.append({
                                                'name': stock['name'],
                                                'Gap': gap,
                                                'stock': stock,
                                                'deviation': deviation,
                                                'below_min_band': below_min_band,
                                                'below_target': below_target,
                                                'invest': 0.0
                                            })
                                        
                                        # Phase B: Priority for assets below the minimum band (Emergency)
                                        total_needed_band = 0.0
                                        for item in stock_data_p:
                                            if item['below_min_band']:
                                                min_band_eur = total_theoretical * ((item['stock']['target_allocation'] - item['stock'].get('tolerance', 0.0)) / 100.0)
                                                needed = max(0.0, min_band_eur - item['stock']['current_value'])
                                                item['needed_band'] = needed
                                                total_needed_band += needed
                                            else:
                                                item['needed_band'] = 0.0
                                                
                                        if total_needed_band > 0 and remaining_investment > 0:
                                            if total_needed_band <= remaining_investment:
                                                for item in stock_data_p:
                                                    if item['needed_band'] > 0:
                                                        alloc = item['needed_band']
                                                        item['invest'] += alloc
                                                        remaining_investment -= alloc
                                            else:
                                                # Proportional distribution of emergency funds
                                                emergency_funds = remaining_investment
                                                for item in stock_data_p:
                                                    if item['needed_band'] > 0:
                                                        prop_alloc = (item['needed_band'] / total_needed_band) * emergency_funds
                                                        item['invest'] += prop_alloc
                                                remaining_investment = 0.0
                                        
                                        # Phase C: Proportional Gap Filling
                                        if remaining_investment > 0 and sum_positive_deviations > 0:
                                            funds_left = remaining_investment
                                            proportions = []
                                            for item in stock_data_p:
                                                if item['below_target']:
                                                    prop_alloc = (item['deviation'] / sum_positive_deviations) * funds_left
                                                    max_inv = max(0.0, item['Gap'] - item['invest'])
                                                    ideal_invest = min(prop_alloc, max_inv)
                                                    proportions.append({'item': item, 'ideal': ideal_invest})
                                            
                                            for p in proportions:
                                                p['item']['invest'] += p['ideal']
                                                remaining_investment -= p['ideal']
                                                
                                        # Phase D: Leftover gap filling
                                        if remaining_investment >= 0.01:
                                            sorted_gaps = sorted(stock_data_p, key=lambda x: x['Gap'] - x['invest'], reverse=True)
                                            for g in sorted_gaps:
                                                if remaining_investment < 0.01: break
                                                needed = max(0.0, g['Gap'] - g['invest'])
                                                if needed > 0:
                                                    alloc = min(remaining_investment, needed)
                                                    g['invest'] += alloc
                                                    remaining_investment -= alloc
                                                    
                                        # Update final investments from the processing pool
                                        for item in stock_data_p:
                                            final_investments[item['name']] = item['invest']
     
                                    # --- STEP 3: Post-Processing Rule Enforcement ---
                                    is_dividends_p = "dividend" in selected_portfolio.lower()
                                    if is_dividends_p:
                                        # 1. Enforce Integer/Floor and MinBuy of 5€
                                        total_after_round = 0.0
                                        for ticker, invest in final_investments.items():
                                            if ticker.upper() == "RENE.PT":
                                                # RENE is already processed/múltiplo do preço
                                                total_after_round += invest
                                                continue
                                                
                                            # Others: Round down to integer euros
                                            rounded_invest = float(math.floor(invest))
                                            
                                            # MinBuy enforcement for PT stocks
                                            if ticker.upper().endswith(".PT") and rounded_invest < 5.0 and rounded_invest > 0:
                                                rounded_invest = 0.0
                                                
                                            final_investments[ticker] = rounded_invest
                                            total_after_round += rounded_invest
                                            
                                        # 2. Redistribution of Cents ("The Dump")
                                        # All remaining budget (including cents from RENE and floors) goes to the largest investment
                                        final_remaining = current_monthly_base - total_after_round
                                        if final_remaining > 0:
                                            dump_ticker = max(final_investments, key=final_investments.get)
                                            final_investments[dump_ticker] += final_remaining
                                            remaining_investment = 0.0
                                        else:
                                            remaining_investment = final_remaining
                                    else:
                                        # Standard Portfolios (Non-Dividends)
                                        # Just apply floor to all (as per previous standard logic)
                                        total_after_round = 0.0
                                        for ticker, invest in final_investments.items():
                                            rounded = float(math.floor(invest))
                                            final_investments[ticker] = rounded
                                            total_after_round += rounded
                                        
                                        # For standard, we usually just keep the remaining in the wallet or dump it 
                                        # to the largest gap if small. Let's keep it consistent.
                                        final_remaining = current_monthly_base - total_after_round
                                        if final_remaining >= 1.0:
                                            # Use standard "largest gap" redistribution for whole euros
                                            sorted_gaps = sorted(final_investments.keys(), key=lambda x: next((s['target_allocation'] for s in live_stocks if s['name']==x), 0), reverse=True)
                                            if sorted_gaps:
                                                final_investments[sorted_gaps[0]] += float(math.floor(final_remaining))
                                    invest_map = final_investments

                                    # --- END EXISTING LOGIC ---
                                
                                # --- COMMON DISPLAY LOGIC ---
                                allocations = []
                                new_total_actual = float(total_current_live + current_monthly_base)
                                new_total_theoretical = total_current_live + current_monthly_base # Ensure defined
                                
                                for stock in live_stocks:
                                    ticker = stock['name']
                                    final_invest = invest_map.get(ticker, 0.0)
                                    target_val = new_total_theoretical * (stock['target_allocation'] / 100.0)
                                    new_val = stock['current_value'] + final_invest
                                    
                                    allocations.append({
                                        "Stock": ticker, 
                                        "Current Value": stock['current_value'], 
                                        "Current %": (stock['current_value'] / total_current_live * 100) if total_current_live > 0 else 0, 
                                        "TER %": stock.get('expense_ratio', 0.0),
                                        "Target %": stock['target_allocation'], 
                                        "Target Value": target_val,
                                        "Investment": final_invest, 
                                        "New Value": new_val, 
                                        "New %": (new_val / new_total_actual * 100) if new_total_actual > 0 else 0
                                    })
                                
                                alloc_df = pd.DataFrame(allocations)
                                if not alloc_df.empty:
                                    custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "PRAB.DE", "EGLN.UK"]
                                    alloc_df['order_idx'] = alloc_df['Stock'].apply(lambda x: custom_order_list.index(x) if x in custom_order_list else 99)
                                    alloc_df = alloc_df.sort_values(by='order_idx').drop(columns=['order_idx'])

                                st.session_state.last_calculation = {"df": alloc_df, "monthly_investment": current_monthly_base, "remaining": remaining_investment}
                                st.session_state.show_recommendations = True
                                
                                # Persist vault allocations per portfolio so the Hedges tab can aggregate them
                                if 'vault_alloc_by_portfolio' not in st.session_state:
                                    st.session_state.vault_alloc_by_portfolio = {}
                                st.session_state.vault_alloc_by_portfolio[selected_portfolio] = {
                                    "type": p_type,
                                    "EGNL.UK": final_investments.get("EGNL.UK", 0.0),
                                    "IBTE.UK": final_investments.get("IBTE.UK", 0.0),
                                }
                        
                        if st.session_state.show_recommendations:
                            # st.divider()
                            calc = st.session_state.last_calculation
                            if calc['remaining'] > 0.01:
                                st.warning(f"Note: €{calc['remaining']:.2f} could not be allocated.")
                            st.success("Allocation Calculated!")
        
                # --- Bottom Row: Results & Visualization ---
                if st.session_state.show_recommendations:
                    with st.container(border=True):
                        st.subheader("📋 Investment Recommendations")
                        df = st.session_state.last_calculation['df']
                        
                        # Create a display-only version by dropping columns requested by user
                        display_df = df.drop(columns=["TER %", "Target Value"])
                        
                        def style_rows(row):
                            base = ''
                            if row['Stock'] in ['WTEQ.DE', 'VDIV.DE', 'JMT.PT', 'EDP.PT']:
                                invest_style = 'background-color: #2563EB; color: white; font-weight: 700; border-bottom: 1px solid #1E3A8A;'
                            else:
                                invest_style = 'background-color: #24A16F; color: white; font-weight: 700; border-bottom: 1px solid #065F46;'
                                
                            return [invest_style if col == 'Investment' else base for col in row.index]
                        
                        styled_df = display_df.style.format(precision=2).apply(style_rows, axis=1)
                        # Use st.dataframe for responsive horizontal scrolling
                        st.dataframe(styled_df, use_container_width=True, hide_index=True)
                        
                        if st.button("💾 Log to History", width="stretch"):
                            with st.spinner("Logging..."):
                                try:
                                    log_rows = df.copy()
                                    log_rows['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    log_rows['username'] = username
                                    log_rows['portfolio_name'] = selected_portfolio
                                    cols_to_log = ['timestamp', 'username', 'portfolio_name', 'Stock', 'Current Value', 'Current %', 'Target %', 'Target Value', 'Investment', 'New Value', 'New %']
                                    log_df = log_rows[cols_to_log]
                                    try: existing_history = conn.read(worksheet="InvestmentLog", ttl=0)
                                    except: existing_history = pd.DataFrame()
                                    new_history = pd.concat([existing_history, log_df], ignore_index=True) if existing_history is not None and not existing_history.empty else log_df
                                    conn.update(worksheet="InvestmentLog", data=new_history)

                                    # --- APPLY NEW VALUES TO PORTFOLIO ---
                                    master_data = st.session_state.master_data.copy()
                                    # Update master_data with New Value for each stock in the current portfolio
                                    for _, row in df.iterrows():
                                        stock_ticker = row['Stock']
                                        new_val = row['New Value']
                                        
                                        mask = (master_data['username'] == username) & \
                                               (master_data['portfolio_name'] == selected_portfolio) & \
                                               (master_data['stock_name'] == stock_ticker)
                                        
                                        if mask.any():
                                            master_data.loc[mask, 'current_value'] = new_val
                                    
                                    # Push updated Portfolio data back to GSheets
                                    conn.update(worksheet="Portfolios", data=master_data)
                                    st.session_state.master_data = master_data
                                    
                                    st.session_state.show_log_success = True
                                    
                                    # Force re-sync of local state so the table reflects the new values
                                    if 'last_selected_portfolio' in st.session_state:
                                        del st.session_state.last_selected_portfolio
                                    st.rerun()
                                except Exception as e: st.error(f"Error: {e}")
                        
                        if st.session_state.get('show_log_success'):
                            st.markdown("<br>", unsafe_allow_html=True)
                            st.success("Logged & Portfolio Updated!")
                            st.balloons()
                            st.session_state.show_log_success = False
        
                    # Charts Row
                    with st.container(border=True):
                        st.subheader("📉 Allocation Visuals")
                        df_plot = df[~df['Stock'].isin(["EGLN.UK", "PRAB.DE"])].sort_values('Stock')
                        
                        fig_after = px.pie(df_plot, values='New Value', names='Stock', hole=0.75, color_discrete_sequence=CHART_PALETTE)
                        fig_after.update_layout(
                            title=dict(
                                text="<b>After Investment</b>",
                                x=0.5,
                                y=0.96,
                                xanchor='center',
                                yanchor='top',
                                font=dict(size=18, color='white')
                            ),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            margin=dict(t=110, b=50, l=40, r=40),
                            showlegend=False,
                            height=480
                        )
                        fig_after.update_traces(
                            sort=False,
                            domain=dict(y=[0.0, 0.85]),
                            textposition='outside',
                            texttemplate="<b>%{label}</b><br>%{value:,.2f} € | %{percent}", 
                            textfont=dict(size=14),
                            hovertemplate="<b>%{label}</b><br>Value: €%{value:,.2f}<br>Weight: %{percent}<extra></extra>",
                            marker=dict(line=dict(color='rgba(0,0,0,0)', width=0))
                        )
                        st.plotly_chart(fig_after, use_container_width=True)



        if "📈 Portfolio Details" in tab_map:
            with tab_map["📈 Portfolio Details"]:
                st.session_state.footer_msg = "<b>Data Insight:</b> Visualize your diversification and asset health."
                uninvested_cash = float(st.session_state.get(f"{selected_portfolio}_uninvested_cash", 0.0))
                if uninvested_cash > 0:
                    st.info(f"💡 You have **€{uninvested_cash:,.2f}** of uninvested cash. You can manage it in the 'Uninvested Cash' tab.", icon="🪙")
                    
                with st.container(border=True):
                    st.subheader("📈 Detailed Portfolio Information")
                    
                    # Prepare data for Detailed Editor
                    df_key = f"{selected_portfolio}_detailed_df"
                    
                    display_cols = {
                        "name": "Ticker",
                        "full_name": "Name",
                        "sector": "Sector",
                        "industry": "Industry",
                        "country": "Country",
                        "currency": "Currency",
                        "current_value": "Market Value",
                        "current_price": "Invested Value (€)",
                        "quantity": "Quantity",
                        "average_price": "Avg. Price",
                        "dividend_yield": "Div. Yield (%)"
                    }

                    # Calculate total dividends received per ticker
                    df_divs = st.session_state.dividends
                    dividend_map = {}
                    if not df_divs.empty:
                        df_divs['amount'] = pd.to_numeric(df_divs['amount'], errors='coerce').fillna(0.0)
                        mask = (df_divs['username'] == username) & (df_divs['portfolio_name'] == selected_portfolio)
                        my_divs = df_divs[mask]
                        dividend_map = my_divs.groupby('ticker')['amount'].sum().to_dict()

                    details_df = pd.DataFrame(st.session_state.stocks)
                    if details_df.empty:
                        details_df = pd.DataFrame(columns=["name", "full_name", "sector", "industry", "country", "currency", "current_value", "quantity", "average_price", "dividend_yield"])
                    
                    # Ensure current_price exists (used as Invested Value in EUR for Stocks portfolio)
                    if 'current_price' not in details_df.columns:
                        details_df['current_price'] = 0.0

                    # Helper to infer country and currency from ticker suffix (e.g., INTC.US -> (USA, USD))
                    def infer_country_and_currency(ticker):
                        if not isinstance(ticker, str) or not ticker:
                            return "", ""
                        parts = ticker.strip().split(".")
                        if len(parts) < 2:
                            return "USA", "USD"
                        suffix = parts[-1].strip().upper()
                        mapping = {
                            "US": ("USA", "USD"),
                            "DE": ("Germany", "EUR"),
                            "DK": ("Denmark", "DKK"),
                            "UK": ("United Kingdom", "GBP"),
                            "GB": ("United Kingdom", "GBP"),
                            "FR": ("France", "EUR"),
                            "NL": ("Netherlands", "EUR"),
                            "IT": ("Italy", "EUR"),
                            "ES": ("Spain", "EUR"),
                            "CA": ("Canada", "CAD"),
                            "CH": ("Switzerland", "CHF"),
                            "JP": ("Japan", "JPY"),
                            "AU": ("Australia", "AUD"),
                            "SE": ("Sweden", "SEK"),
                            "NO": ("Norway", "NOK"),
                            "FI": ("Finland", "EUR"),
                            "BE": ("Belgium", "EUR"),
                            "PT": ("Portugal", "EUR"),
                            "IE": ("Ireland", "EUR"),
                            "BR": ("Brazil", "BRL"),
                            "CN": ("China", "CNY"),
                            "HK": ("Hong Kong", "HKD"),
                            "IN": ("India", "INR"),
                        }
                        return mapping.get(suffix, (suffix, "USD"))

                    # Dynamically infer and populate country & currency from ticker
                    if not details_df.empty and 'name' in details_df.columns:
                        inferred = details_df['name'].apply(infer_country_and_currency)
                        details_df['country'] = inferred.apply(lambda x: x[0])
                        details_df['currency'] = inferred.apply(lambda x: x[1])

                    # Filtering only the requested columns and renaming
                    details_display_df = details_df[list(display_cols.keys())].rename(columns=display_cols)

                    # Yield on Cost = Dividend Yield × (Market Value / Invested Value)
                    # Both Market Value and Invested Value are in EUR — no currency mixing
                    def calc_yoc(row):
                        try:
                            current_val = float(row.get('current_value', 0.0) or 0.0)
                            invested = float(row.get('current_price', 0.0) or 0.0)
                            div_yield = float(row.get('dividend_yield', 0.0) or 0.0)
                            if invested <= 0:
                                return 0.0
                            return (div_yield / 100.0) * (current_val / invested) * 100.0
                        except (ValueError, TypeError, ZeroDivisionError):
                            return 0.0



                    # Received Yield on Cost (%) = (Dividends Received / Invested Value) * 100
                    def calc_received_yoc(row):
                        try:
                            ticker = row.get('name', '')
                            divs = float(dividend_map.get(ticker, 0.0))
                            invested = float(row.get('current_price', 0.0) or 0.0)
                            if invested <= 0:
                                return 0.0
                            return (divs / invested) * 100.0
                        except:
                            return 0.0

                    details_display_df['YoC (%)'] = details_df.apply(calc_yoc, axis=1)
                    details_display_df['Received YoC (%)'] = details_df.apply(calc_received_yoc, axis=1)

                    # Add Current % Calculation (read-only)
                    total_p_val = details_df['current_value'].sum()
                    details_display_df['Current %'] = (details_df['current_value'] / total_p_val * 100) if total_p_val > 0 else 0

                    # Explicitly reorder columns to place "Current %" before "Market Value"
                    desired_order = [
                        "Ticker", "Name", "Sector", "Industry", "Country", "Currency", 
                        "Current %", "Market Value", "Invested Value (€)", "Quantity", 
                        "Avg. Price", "Div. Yield (%)", "YoC (%)", "Received YoC (%)"
                    ]
                    col_order = [c for c in desired_order if c in details_display_df.columns]
                    details_display_df = details_display_df[col_order]

                    # Freeze Ticker by setting as Index
                    details_display_df.set_index("Ticker", inplace=True)

                    detailed_config = {
                        "Name": st.column_config.TextColumn("Name"),
                        "Market Value": st.column_config.NumberColumn("Market Value (€)", min_value=0.0, step=0.01, format="€%.2f"),
                        "Invested Value (€)": st.column_config.NumberColumn("Invested Value (€)", min_value=0.0, step=0.01, format="€%.2f"),
                        "Current %": st.column_config.NumberColumn("Current %", format="%.2f%%", disabled=True),
                        "Quantity": st.column_config.NumberColumn("Quantity", format="%.2f"),
                        "Avg. Price": st.column_config.NumberColumn("Avg. Price", min_value=0.0, step=0.01, format="%.2f"),
                        "Div. Yield (%)": st.column_config.NumberColumn("Div. Yield (%)", format="%.2f%%"),
                        "Sector": st.column_config.TextColumn("Sector"),
                        "Industry": st.column_config.TextColumn("Industry"),
                        "Country": st.column_config.TextColumn("Country", disabled=True),
                        "Currency": st.column_config.TextColumn("Currency", disabled=True),
                        "YoC (%)": st.column_config.NumberColumn("YoC (%)", format="%.2f%%", disabled=True),
                        "Received YoC (%)": st.column_config.NumberColumn("Received YoC (%)", format="%.2f%%", disabled=True),
                    }
                    
                    edited_details_df = st.data_editor(
                        details_display_df,
                        column_config=detailed_config,
                        use_container_width=True,
                        num_rows="dynamic",
                        key=f"details_editor_{st.session_state.editor_key}",
                        on_change=clear_recommendations
                    )
                    
                    # Sync back to session state if edited
                    if not edited_details_df.sort_index().equals(details_display_df.sort_index()):
                        # Map back renamed columns to internal keys
                        reverse_cols = {v: k for k, v in display_cols.items()}
                        # Reset index to get Ticker back into columns before renaming
                        updated_details = edited_details_df.reset_index().rename(columns=reverse_cols)
                        
                        new_stocks_list = []
                        # Existing stocks map to preserve internal rebalancing fields
                        current_stocks_map = {s['name']: s for s in st.session_state.stocks}
                        
                        for _, row in updated_details.iterrows():
                            ticker_val = row['name']
                            ticker = str(ticker_val).strip().upper() if pd.notna(ticker_val) else ""
                            if not ticker or ticker.lower() in ["nan", "none"]:
                                continue
                                
                            # If existing, update numeric and metadata fields
                            if ticker in current_stocks_map:
                                updated_stock = current_stocks_map[ticker].copy()
                                for col in updated_details.columns:
                                    if col in ('name', 'Current %', 'YoC (%)', 'Received YoC (%)'):
                                        pass  # Skip computed/key columns
                                    elif col == 'average_price':
                                        # Save avg_price as plain float (native currency, independent)
                                        try:
                                            updated_stock['average_price'] = float(row[col] or 0.0)
                                        except (ValueError, TypeError):
                                            pass
                                    elif col == 'current_price':
                                        # Save invested_value_eur directly, no cross-computation
                                        try:
                                            updated_stock['current_price'] = float(row[col] or 0.0)
                                        except (ValueError, TypeError):
                                            pass
                                    else:
                                        updated_stock[col] = row[col]
                                new_stocks_list.append(updated_stock)
                            else:
                                # New row added directly in editor
                                new_stock = {
                                    "name": ticker,
                                    "current_value": float(row.get('current_value', 0.0) or 0.0),
                                    "current_price": float(row.get('current_price', 0.0) or 0.0),
                                    "target_allocation": 0.0,
                                    "tolerance": 2.0,
                                    "expense_ratio": 0.0,
                                    "full_name": row.get('full_name', ''),
                                    "sector": row.get('sector', ''),
                                    "industry": row.get('industry', ''),
                                    "country": row.get('country', ''),
                                    "currency": row.get('currency', 'EUR'),
                                    "quantity": float(row.get('quantity', 0.0) or 0.0),
                                    "average_price": float(row.get('average_price', 0.0) or 0.0),
                                    "dividend_yield": float(row.get('dividend_yield', 0.0) or 0.0),
                                }
                                new_stocks_list.append(new_stock)
                        
                        if len(new_stocks_list) < len(st.session_state.stocks):
                            # Identify deleted items
                            updated_names = {s['name'] for s in new_stocks_list}
                            deleted_items = [s for s in st.session_state.stocks if s['name'] not in updated_names]
                            st.session_state.undo_buffer = deleted_items
                            st.session_state.show_undo = True
                            st.toast(f"Deleted {len(deleted_items)} stock(s)", icon="🗑️")
                        else:
                            st.session_state.show_undo = False
                            st.session_state.undo_buffer = []

                        st.session_state.stocks = new_stocks_list
                        st.session_state.has_unsaved_changes = True
                        st.rerun()

                # UNDO AND SAVE BUTTONS
                u_col, s_col = st.columns([1, 1])
                with u_col:
                    if st.session_state.get('show_undo'):
                        if st.button("↩️ Undo Delete", key="undo_details_btn", width="stretch"):
                            if st.session_state.undo_buffer:
                                st.session_state.stocks.extend(st.session_state.undo_buffer)
                                st.session_state.undo_buffer = []
                                st.session_state.show_undo = False
                                st.session_state.editor_key += 1
                                st.toast("Restored deleted stocks!", icon="✅")
                                st.rerun()
                
                with s_col:
                    if st.button("💾 Save All Changes", key="save_details_btn", width="stretch"):
                        # Determine current portfolio config
                        portfolio_invest = st.session_state.get(f"{selected_portfolio}_monthly_invest", 1000.0)
                        portfolio_use_ind = st.session_state.get(f"{selected_portfolio}_use_indicators", False)
                        portfolio_buffett = st.session_state.get(f"{selected_portfolio}_buffett_index", 195.0)
                        portfolio_birth_date = st.session_state.get(f"{selected_portfolio}_birth_date", "")
                        try:
                            portfolio_uninvested_cash = float(st.session_state.get(f"{selected_portfolio}_uninvested_cash", 0.0))
                        except:
                            portfolio_uninvested_cash = 0.0
                        portfolio_type = p_type
                        
                        mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        data = data[~mask]
                        
                        new_rows = []
                        for s in st.session_state.stocks:
                            if s['name'] and s['name'] != "__PLACEHOLDER__":
                                new_rows.append({
                                    "username": username,
                                    "portfolio_name": selected_portfolio,
                                    "stock_name": s['name'],
                                    "current_value": s['current_value'],
                                    "current_price": float(s.get('current_price', 0.0) or 0.0),
                                    "target_allocation": s.get('target_allocation', 0.0),
                                    "tolerance": s.get('tolerance', 2.0),
                                    "expense_ratio": s.get('expense_ratio', 0.0),
                                    "portfolio_monthly_invest": portfolio_invest,
                                    "portfolio_use_indicators": portfolio_use_ind,
                                    "portfolio_buffett_index": portfolio_buffett,
                                    "portfolio_uninvested_cash": portfolio_uninvested_cash,
                                    "portfolio_type": portfolio_type,
                                    "stock_full_name": s.get('full_name', ''),
                                    "sector": s.get('sector', ''),
                                    "industry": s.get('industry', ''),
                                    "country": s.get('country', ''),
                                    "currency": s.get('currency', ''),
                                    "quantity": float(s.get('quantity', 0.0)),
                                    "average_price": float(s.get('average_price', 0.0)),
                                    "dividend_yield": float(s.get('dividend_yield', 0.0))
                                })
                        
                        if not new_rows:
                            new_rows.append({
                                "username": username,
                                "portfolio_name": selected_portfolio,
                                "stock_name": "__PLACEHOLDER__",
                                "current_value": 0.0,
                                "target_allocation": 0.0,
                                "current_price": 0.0,
                                "portfolio_monthly_invest": portfolio_invest,
                                "portfolio_use_indicators": portfolio_use_ind,
                                "portfolio_buffett_index": portfolio_buffett,
                                "portfolio_birth_date": portfolio_birth_date,
                                "portfolio_uninvested_cash": portfolio_uninvested_cash,
                                "portfolio_type": portfolio_type,
                                "stock_full_name": '', "sector": '', "industry": '', "country": '', "currency": '', "quantity": 0.0, "average_price": 0.0, "dividend_yield": 0.0
                            })
                        
                        updated_data = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)
                        
                        st.session_state.editor_key += 1
                        st.session_state.has_unsaved_changes = False
                        st.session_state.show_save_success = True
                        st.balloons()
                        st.rerun()

                if st.session_state.get('show_save_success'):
                    st.success("All changes saved successfully!")
                    st.session_state.show_save_success = False

                # Distribution Charts
                with st.container(border=True):
                    st.subheader("🌍 Portfolio Distributions")
                    
                    # Clean data for plotting (remove placeholders and empty values)
                    plot_data = pd.DataFrame([s for s in st.session_state.stocks if s['name'] != "__PLACEHOLDER__"])
                    
                    if not plot_data.empty:
                        chart_theme = dict(
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color='white', size=13),
                            height=400,
                            margin=dict(t=40, b=40, l=80, r=80),
                            showlegend=False
                        )
                        
                        # Use Tabs to provide massive horizontal workspace for Plotly leader lines
                        dist_tab1, dist_tab2, dist_tab3, dist_tab4 = st.tabs(["📊 By Stock", "🏭 By Sector", "🏢 By Industry", "📍 By Country"])
                        
                        with dist_tab1:
                            # Current % (Asset Distribution)
                            asset_data = plot_data.groupby('name')['current_value'].sum().reset_index()
                            asset_data = asset_data[asset_data['current_value'] > 0]
                            if not asset_data.empty:
                                asset_data = asset_data.sort_values(by='current_value', ascending=False)
                                fig_asset = px.pie(asset_data, values='current_value', names='name', hole=0.75, color_discrete_sequence=CHART_PALETTE)
                                fig_asset.update_layout(chart_theme)
                                fig_asset.update_traces(textposition='outside', texttemplate="<b>%{label}</b><br>%{value:,.2f} € | %{percent}", textfont=dict(size=15), hovertemplate="<b>%{label}</b><br>Value: €%{value:,.2f}<br>Weight: %{percent}<extra></extra>", marker=dict(line=dict(color='rgba(0,0,0,0)', width=0)))
                                st.plotly_chart(fig_asset, use_container_width=True)
                            else:
                                st.info("No asset data available.")

                        with dist_tab2:
                            # Sector Distribution
                            sector_data = plot_data.groupby('sector')['current_value'].sum().reset_index()
                            sector_data = sector_data[sector_data['sector'] != '']
                            if not sector_data.empty:
                                fig_sector = px.pie(sector_data, values='current_value', names='sector', hole=0.75, color_discrete_sequence=CHART_PALETTE)
                                fig_sector.update_layout(chart_theme)
                                fig_sector.update_traces(textposition='outside', texttemplate="<b>%{label}</b><br>%{value:,.2f} € | %{percent}", textfont=dict(size=15), hovertemplate="<b>%{label}</b><br>Value: €%{value:,.2f}<br>Weight: %{percent}<extra></extra>", marker=dict(line=dict(color='rgba(0,0,0,0)', width=0)))
                                st.plotly_chart(fig_sector, use_container_width=True)
                            else:
                                st.info("No sector data available.")
                                
                        with dist_tab3:
                            # Industry Distribution
                            ind_data = plot_data.groupby('industry')['current_value'].sum().reset_index()
                            ind_data = ind_data[ind_data['industry'] != '']
                            if not ind_data.empty:
                                fig_ind = px.pie(ind_data, values='current_value', names='industry', hole=0.75, color_discrete_sequence=CHART_PALETTE)
                                fig_ind.update_layout(chart_theme)
                                fig_ind.update_traces(textposition='outside', texttemplate="<b>%{label}</b><br>%{value:,.2f} € | %{percent}", textfont=dict(size=15), hovertemplate="<b>%{label}</b><br>Value: €%{value:,.2f}<br>Weight: %{percent}<extra></extra>", marker=dict(line=dict(color='rgba(0,0,0,0)', width=0)))
                                st.plotly_chart(fig_ind, use_container_width=True)
                            else:
                                st.info("No industry data available.")
                                
                        with dist_tab4:
                            # Country Distribution
                            country_data = plot_data.groupby('country')['current_value'].sum().reset_index()
                            country_data = country_data[country_data['country'] != '']
                            if not country_data.empty:
                                fig_country = px.pie(country_data, values='current_value', names='country', hole=0.75, color_discrete_sequence=CHART_PALETTE)
                                fig_country.update_layout(chart_theme)
                                fig_country.update_traces(textposition='outside', texttemplate="<b>%{label}</b><br>%{value:,.2f} € | %{percent}", textfont=dict(size=15), hovertemplate="<b>%{label}</b><br>Value: €%{value:,.2f}<br>Weight: %{percent}<extra></extra>", marker=dict(line=dict(color='rgba(0,0,0,0)', width=0)))
                                st.plotly_chart(fig_country, use_container_width=True)
                            else:
                                st.info("No country data available.")
                    else:
                        st.info("Add stocks to see distributions.")

        if "🪙 Uninvested Cash" in tab_map:
            with tab_map["🪙 Uninvested Cash"]:
                st.subheader("🪙 Uninvested Cash Balance")
                st.write("Keep track of the remaining cents that were not invested during your last rebalancing.")
                
                try:
                    current_uninvested = float(st.session_state.get(f"{selected_portfolio}_uninvested_cash", 0.0))
                except:
                    current_uninvested = 0.0
                    
                if current_uninvested > 0:
                    st.markdown(
                        f"""
                        <div style="padding: 10px 15px; border-radius: 8px; background-color: rgba(255, 139, 118, 0.1); border: 1px solid rgba(255, 139, 118, 0.5); display: inline-block; margin-bottom: 15px;">
                            <div style="font-size: 0.85rem; color: #888; margin-bottom: 4px;">Currently Saved Balance</div>
                            <div style="font-size: 1.8rem; font-weight: 700; color: #FF8B76;">€{current_uninvested:.2f} ⚠️</div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    st.metric("Currently Saved Balance", f"€{current_uninvested:.2f}")
                
                input_col, btn_col, _ = st.columns([2.5, 1.5, 4])
                
                with input_col:
                    new_uninvested = st.number_input(
                        "Update Cash Balance (€)", 
                        min_value=0.0, 
                        value=current_uninvested, 
                        step=0.01,
                        format="%.2f",
                        key=f"{selected_portfolio}_uninvested_input"
                    )
                
                with btn_col:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("💾 Save", width=150):
                        st.session_state[f"{selected_portfolio}_uninvested_cash"] = new_uninvested
                        
                        # Apply to dataframe and save
                        mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                        data.loc[mask, 'portfolio_uninvested_cash'] = new_uninvested
                        
                        try:
                            conn.update(worksheet="Portfolios", data=data)
                            st.session_state.master_data = data
                            st.session_state.show_cash_success = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to save: {e}")
                        
                if st.session_state.get("show_cash_success"):
                    st.success("Cash balance saved successfully! ✅")
                    st.session_state.show_cash_success = False
                        
        if "💰 Dividend Tracker" in tab_map:
            with tab_map["💰 Dividend Tracker"]:
                st.session_state.footer_msg = "<b>Passive Income:</b> Track your dividend yields and growth."
                st.subheader("💰 Dividend Tracker")
                if True: # Record Dividend section
                    with st.container(border=True):
                        st.markdown("### ➕ Record Dividend")
                        from datetime import datetime
                        current_portfolio_stocks = [s['name'] for s in st.session_state.stocks if s['name'] != "__PLACEHOLDER__"]
                        
                        r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                        
                        with r_col1:
                            div_date = st.date_input("Date", value=datetime.today())
                        
                        with r_col2:
                            if not current_portfolio_stocks:
                                st.warning("Add stocks first.")
                                div_ticker = None
                            else:
                                div_ticker = st.selectbox("Ticker", options=current_portfolio_stocks)
                        
                        with r_col3:
                            div_amount = st.number_input("Amount (€)", min_value=0.0, step=0.01)
                        
                        with r_col4:
                            st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                            add_clicked = st.button("Add Record", width="stretch")
                        
                        if add_clicked:
                            if div_ticker and div_amount > 0:
                                new_div = {
                                    "date": str(div_date),
                                    "ticker": div_ticker,
                                    "amount": div_amount,
                                    "portfolio_name": selected_portfolio,
                                    "username": username
                                }
                                new_row_df = pd.DataFrame([new_div])
                                st.session_state.dividends = pd.concat([st.session_state.dividends, new_row_df], ignore_index=True)
                                conn.update(worksheet="Dividends", data=st.session_state.dividends)
                                st.success("Dividend Recorded!")
                                st.rerun()
                            else:
                                st.error("Please select a ticker and enter an amount.")
                
                if True: # Monthly Dividends section
                    with st.container(border=True):
                        st.markdown("### 📈 Monthly Dividends")
                        df_divs = st.session_state.dividends
                        if not df_divs.empty:
                            df_divs['amount'] = pd.to_numeric(df_divs['amount'], errors='coerce').fillna(0.0)
                            df_divs['date'] = pd.to_datetime(df_divs['date'], errors='coerce')
                            mask = (df_divs['username'] == username) & (df_divs['portfolio_name'] == selected_portfolio)
                            my_divs = df_divs[mask].copy()
                            if not my_divs.empty:
                                # Filter for Current and Previous Year only
                                current_year = datetime.now().year
                                my_divs = my_divs[my_divs['date'].dt.year >= (current_year - 1)]
                                
                                if my_divs.empty:
                                    st.info(f"No dividends found for {current_year-1} or {current_year}.")
                                else:
                                    my_divs['Year'] = my_divs['date'].dt.year.astype(str)
                                    
                                    # Ticker Filter
                                    available_tickers = sorted(my_divs['ticker'].unique().tolist())
                                    filter_ticker = st.selectbox("🔍 Filter by Ticker", options=["All Data"] + available_tickers)
                                    
                                    if filter_ticker != "All Data":
                                        my_divs = my_divs[my_divs['ticker'] == filter_ticker]
                                        if my_divs.empty:
                                            st.warning(f"No data for {filter_ticker} in the selected period.")
                                            st.stop()
                                
                                    # Calculate Yearly Totals
                                    current_year_str = str(current_year)
                                    prev_year_str = str(current_year - 1)
                                    
                                    total_current_year = my_divs[my_divs['Year'] == current_year_str]['amount'].sum()
                                    total_prev_year = my_divs[my_divs['Year'] == prev_year_str]['amount'].sum()
                                    
                                    # Display Totals Side-by-Side
                                    metric_col1, metric_col2 = st.columns(2)
                                    with metric_col1:
                                        st.markdown(f"<div style='margin-bottom: 15px;'><span style='font-size: 1.1rem; font-weight: 600; color: #E5E7EB;'>💰 Total Dividends ({current_year})</span><br><span style='font-size: 2rem; font-weight: 700;'>€{total_current_year:,.2f}</span></div>", unsafe_allow_html=True)
                                    with metric_col2:
                                        st.markdown(f"<div style='margin-bottom: 15px;'><span style='font-size: 1.1rem; font-weight: 600; color: #E5E7EB;'>💰 Total Dividends ({current_year-1})</span><br><span style='font-size: 2rem; font-weight: 700;'>€{total_prev_year:,.2f}</span></div>", unsafe_allow_html=True)
                                    
                                    my_divs['Month'] = my_divs['date'].dt.strftime('%b')
                                    my_divs['MonthNum'] = my_divs['date'].dt.month
                                    
                                    # Aggregated stats
                                    actual_stats = my_divs.groupby(['Year', 'Month', 'MonthNum'])['amount'].sum().reset_index()
                                    
                                    # Create a template for all 12 months for BOTH years to ensure a full X-axis
                                    import calendar
                                    all_months = [calendar.month_name[i][:3] for i in range(1, 13)] # ['Jan', 'Feb', ...]
                                    
                                    template_rows = []
                                    for yr in [str(current_year), str(current_year-1)]:
                                        for i, m in enumerate(all_months):
                                            template_rows.append({'Year': yr, 'Month': m, 'MonthNum': i+1})
                                    
                                    template_df = pd.DataFrame(template_rows)
                                    
                                    # Merge actual data into template
                                    monthly_stats = pd.merge(template_df, actual_stats, on=['Year', 'Month', 'MonthNum'], how='left').fillna(0.0)
                                    
                                    # Sort for plotting: Year descending (Previous Year first in group usually depends on plotly, but keeping Month order is key)
                                    monthly_stats = monthly_stats.sort_values(['MonthNum', 'Year'])
                                    monthly_stats['amount'] = monthly_stats['amount'].round(2)
                                    monthly_stats['text_label'] = monthly_stats['amount'].apply(lambda x: f"€{x:,.2f}" if x > 0 else "")
                                    
                                    st.markdown("#### 📊 Dividends Received (Yearly Comparison)")
                                    fig_div = px.bar(monthly_stats, x='Month', y='amount', color='Year', barmode='group', labels={'amount': 'Amount (€)', 'Month': 'Month'}, text='text_label', color_discrete_sequence=CHART_PALETTE)
                                    fig_div.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=20, b=20, l=10, r=10))
                                    fig_div.update_traces(textposition='auto', cliponaxis=False, textangle=-90, textfont_size=20, textfont=dict(color='white'))
                                    fig_div.update_layout(
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=16)),
                                        legend_title=dict(font=dict(size=16)),
                                        font=dict(size=18), 
                                        xaxis=dict(title_font=dict(size=20), tickfont=dict(size=18)),
                                        yaxis=dict(title_font=dict(size=20), tickfont=dict(size=18)),
                                        margin=dict(t=10, b=50, l=10, r=10), 
                                        paper_bgcolor='rgba(0,0,0,0)', 
                                        plot_bgcolor='rgba(0,0,0,0)',
                                        uniformtext=dict(mode='show', minsize=20)
                                    )
                                    st.plotly_chart(fig_div, use_container_width=True, config={'displayModeBar': False})
                                    with st.expander("Dividend History"):
                                        history_df = my_divs[['date', 'ticker', 'amount']].sort_values('date', ascending=False).copy()
                                        history_df['date'] = history_df['date'].dt.date
                                        
                                        # Ensure we have available tickers for the editor
                                        portfolio_tickers = [s['name'] for s in st.session_state.stocks if s['name'] != "__PLACEHOLDER__"]
                                        if filter_ticker != "All Data" and filter_ticker not in portfolio_tickers:
                                            portfolio_tickers.append(filter_ticker)
                                            
                                        edited_history = st.data_editor(
                                            history_df,
                                            column_config={
                                                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                                                "ticker": st.column_config.SelectboxColumn("Ticker", options=portfolio_tickers, required=True),
                                                "amount": st.column_config.NumberColumn("Amount (€)", min_value=0.0, format="€%.2f", required=True),
                                            },
                                            use_container_width=True,
                                            num_rows="dynamic",
                                            key=f"div_history_editor_{st.session_state.get('editor_key', 0)}"
                                        )
                                        
                                        if st.button("💾 Save History Changes", width="stretch", key="save_div_hist"):
                                            old_dividends = st.session_state.dividends.drop(index=my_divs.index)
                                            
                                            new_records = []
                                            for _, row in edited_history.iterrows():
                                                if pd.notna(row['date']) and pd.notna(row['ticker']) and pd.notna(row['amount']):
                                                    try:
                                                        date_str = pd.to_datetime(row['date']).strftime('%Y-%m-%d')
                                                    except:
                                                        date_str = str(row['date'])
                                                    new_records.append({
                                                        "date": date_str,
                                                        "ticker": str(row['ticker']),
                                                        "amount": float(row['amount']),
                                                        "portfolio_name": selected_portfolio,
                                                        "username": username
                                                    })
                                            
                                            if new_records:
                                                new_df = pd.DataFrame(new_records)
                                                curr_divs = pd.concat([old_dividends, new_df], ignore_index=True)
                                            else:
                                                curr_divs = old_dividends.reset_index(drop=True)
                                                
                                            st.session_state.dividends = curr_divs
                                            conn.update(worksheet="Dividends", data=curr_divs)
                                            st.success("History updated!")
                                            st.rerun()
                            else:
                                st.info("No dividends recorded for this portfolio yet.")
                        else:
                            st.info("No dividends recorded yet.")

    else:
        # Welcome Screen
        with st.container(border=True):
            st.markdown('<div style="text-align: center; padding: 30px;">', unsafe_allow_html=True)
            st.markdown("# 👋 Welcome to Your Portfolio Manager")
            st.markdown("### Let's get started with your first investment strategy.")
            st.markdown("""
            1. Use the **sidebar** to create your first portfolio.
            2. Add your favorite stocks and set target weights.
            3. Use our **Market Indicator** intelligence to optimize your risk.
            """)
            if st.button("🚀 Create My First Portfolio Now"):
                st.toast("Check the sidebar to your left!", icon="👈")
            st.markdown('</div>', unsafe_allow_html=True)


