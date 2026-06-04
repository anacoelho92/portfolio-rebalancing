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
from typing import Dict, Any, Optional, List
from uuid import uuid4

# --- PREMIUM CHART COLOR PALETTE ---
CHART_PALETTE = ['#3B82F6', '#10B981', '#F59E0B', '#8B5CF6', '#EC4899', '#14B8A6', '#F43F5E', '#84CC16', '#6366F1', '#0EA5E9']

#########################################################
# Growth — final strategy
#########################################################

RETIREMENT_AGE = 67
WITHDRAWAL_RATE = 0.035

BASE_CONTRIBUTION = 500.0

SPYL_BASE = 55.0
IXUA_BASE = 30.0
VFEA_BASE = 12.0

GD_TICKER_MAP = {
    "SPYL": "SPYL.DE",
    "IXUA": "IXUA.DE",
    "VFEA": "VFEA.DE",
    "GOLD": "EGLN.UK",
}

PORTFOLIO_TYPE_GROWTH = "Growth"
LEGACY_GROWTH_PORTFOLIO_TYPES = {"Unified", "Growth & Dividends"}
LEGACY_GROWTH_PORTFOLIO_NAME = "Growth & Dividends"

GROWTH_ETF_TICKERS = list(GD_TICKER_MAP.values())
GROWTH_DIVIDENDS_TICKERS = GROWTH_ETF_TICKERS  # alias
REMOVED_GD_TICKERS = {"WTEQ.DE", "VDIV.DE", "JMT.PT", "EDP.PT"}
SAFE_LIQUIDITY_LABEL = "Safe Liquidity"
GLOBAL_OVERVIEW_LABEL = "🌍 Global Overview"
DEFAULT_INVESTOR_BIRTH_DATE = "1992-01-01"
DELETE_ICON = ":material/delete:"

PORTFOLIOS_REQUIRED_COLUMNS = [
    "username",
    "stock_name",
    "current_value",
    "target_allocation",
    "portfolio_name",
    "tolerance",
    "expense_ratio",
    "portfolio_monthly_invest",
    "portfolio_use_indicators",
    "portfolio_buffett_index",
    "stock_full_name",
    "sector",
    "industry",
    "country",
    "currency",
    "quantity",
    "average_price",
    "dividend_yield",
    "portfolio_type",
    "portfolio_birth_date",
    "portfolio_uninvested_cash",
    "portfolio_safe_liquidity",
    "portfolio_uninvested_reinvested",
    "current_price",
    "investor_birth_date",
]


def empty_portfolios_dataframe() -> pd.DataFrame:
    return pd.DataFrame(columns=PORTFOLIOS_REQUIRED_COLUMNS)


def filter_master_data_for_user(data: pd.DataFrame, username: str) -> pd.DataFrame:
    if data is None or data.empty or "username" not in data.columns:
        return empty_portfolios_dataframe()
    return data[data["username"] == username].copy()


def filter_master_data_by_portfolio(df: pd.DataFrame, portfolio_name: str) -> pd.DataFrame:
    if df is None or df.empty or "portfolio_name" not in df.columns:
        return empty_portfolios_dataframe()
    return df[df["portfolio_name"] == portfolio_name].copy()


def gold_target(age: int) -> float:
    if age <= 55:
        return 3.0
    if age >= RETIREMENT_AGE:
        return 10.0
    return 3.0 + ((age - 55) / 12.0) * 7.0


def target_weights(age: int) -> Dict[str, float]:
    gold = gold_target(age)
    growth = 100.0 - gold
    base = SPYL_BASE + IXUA_BASE + VFEA_BASE
    return {
        "SPYL": growth * SPYL_BASE / base,
        "IXUA": growth * IXUA_BASE / base,
        "VFEA": growth * VFEA_BASE / base,
        "GOLD": gold,
    }


def growth_targets(age: int) -> Dict[str, float]:
    return target_weights(age)


def growth_targets_by_ticker(age: int) -> Dict[str, float]:
    raw = target_weights(age)
    return {GD_TICKER_MAP[key]: raw[key] for key in raw}


def cash_split(age: int) -> float:
    if age < 60:
        return 0.0
    if age < 62:
        return 0.2
    if age < 64:
        return 0.4
    if age < 66:
        return 0.6
    if age < RETIREMENT_AGE:
        return 0.8
    return 1.0


def monthly_contribution(month: Optional[int] = None) -> float:
    m = month if month is not None else date.today().month
    if m in (6, 12):
        return BASE_CONTRIBUTION * 2
    return BASE_CONTRIBUTION


def planned_monthly_contribution(month: Optional[int] = None) -> float:
    return monthly_contribution(month)


def calculate_portfolio_targets(age: int) -> Dict[str, Any]:
    targets = growth_targets_by_ticker(age)
    total = sum(targets.values())
    if abs(total - 100.0) > 0.01:
        raise ValueError(f"Portfolio targets do not sum to 100%. Total = {total:.2f}%")
    return {
        "age": age,
        "targets": round_weights(targets, 2),
        "cash_split": cash_split(age),
        "gold_target_pct": round(gold_target(age), 2),
        "is_retired": age >= RETIREMENT_AGE,
        "annual_withdrawal_rate": WITHDRAWAL_RATE,
        "total": round(total, 2),
    }


def annual_withdrawal(portfolio_value: float) -> float:
    return round(portfolio_value * WITHDRAWAL_RATE, 2)


def compute_delta(
    current_values: Dict[str, float],
    age: int,
) -> Dict[str, float]:
    """Target % minus current % for each asset (positive = underweight)."""
    targets = growth_targets_by_ticker(age)
    all_assets = list(targets.keys())
    portfolio_value = sum(current_values.get(asset, 0.0) for asset in all_assets)
    if portfolio_value <= 0:
        current_weights = {asset: 0.0 for asset in all_assets}
    else:
        current_weights = {
            asset: current_values.get(asset, 0.0) / portfolio_value * 100.0
            for asset in all_assets
        }
    return {
        asset: targets[asset] - current_weights[asset]
        for asset in all_assets
    }


def sell_proportionally(
    current_values: Dict[str, float],
    amount: float,
) -> Dict[str, float]:
    portfolio_value = sum(current_values.values())
    if amount <= 0 or portfolio_value <= 0:
        return {}
    return {
        ticker: round(amount * value / portfolio_value, 2)
        for ticker, value in current_values.items()
        if value > 0
    }


def withdraw(
    current_values: Dict[str, float],
    age: int,
    amount: float,
) -> Dict[str, Any]:
    """
    ETF sales for a retirement shortfall: sell from overweight assets (negative
    delta), proportional to excess vs target; fallback to proportional sell.
    """
    targets = growth_targets_by_ticker(age)
    delta = compute_delta(current_values, age)
    excess_assets = [asset for asset in delta if delta[asset] < 0]
    excess_total = sum(-delta[asset] for asset in excess_assets)

    sells = {asset: 0.0 for asset in targets}
    remaining = round(float(amount), 2)

    if excess_total > 0:
        for asset in excess_assets:
            weight = (-delta[asset]) / excess_total
            sell_amount = round(amount * weight, 2)
            sells[asset] = sell_amount
            remaining = round(remaining - sell_amount, 2)

    fallback_sells: Dict[str, float] = {}
    if remaining > 0:
        fallback_sells = sell_proportionally(current_values, remaining)
        for ticker, sell_amount in fallback_sells.items():
            sells[ticker] = round(sells.get(ticker, 0.0) + sell_amount, 2)
        remaining = 0.0

    etf_sells = {ticker: amt for ticker, amt in sells.items() if amt > 0}
    return {
        "portfolio_value": round(sum(current_values.values()), 2),
        "withdrawal_amount": round(amount, 2),
        "delta": round_weights(delta, 2),
        "excess_assets": excess_assets,
        "etf_sells": etf_sells,
        "fallback_sells": fallback_sells,
        "used_proportional_fallback": bool(fallback_sells),
        "remaining_unallocated": remaining,
    }


def retirement_withdrawal_plan(
    current_values: Dict[str, float],
    age: int,
    cash_buffer: float = 0.0,
) -> Dict[str, Any]:
    etf_value = sum(current_values.values())
    safe_liquidity = max(0.0, float(cash_buffer))
    total_value = etf_value + safe_liquidity
    amount = annual_withdrawal(total_value)
    from_buffer = round(min(amount, safe_liquidity), 2)
    shortfall = round(max(0.0, amount - from_buffer), 2)

    etf_plan: Dict[str, Any] = {
        "etf_sells": {},
        "excess_assets": [],
        "delta": {},
        "used_proportional_fallback": False,
        "fallback_sells": {},
    }
    if shortfall > 0:
        etf_plan = withdraw(current_values, age, shortfall)

    return {
        "portfolio_value": round(total_value, 2),
        "etf_value": round(etf_value, 2),
        "safe_liquidity": round(safe_liquidity, 2),
        "withdrawal_amount": amount,
        "from_cash_buffer": from_buffer,
        "shortfall": shortfall,
        "annual_withdrawal_rate": WITHDRAWAL_RATE,
        "etf_sells": etf_plan.get("etf_sells", {}),
        "excess_assets": etf_plan.get("excess_assets", []),
        "delta": etf_plan.get("delta", {}),
        "used_proportional_fallback": etf_plan.get("used_proportional_fallback", False),
        "fallback_sells": etf_plan.get("fallback_sells", {}),
    }


# =========================
# Unified Portfolio Helpers & Allocation Logic
# =========================

def round_weights(weights: Dict[str, float], decimals: int = 2) -> Dict[str, float]:
    return {asset: round(weight, decimals) for asset, weight in weights.items()}


def apply_cents_to_largest_investment(
    investments: Dict[str, float],
    total_budget: float,
) -> Dict[str, float]:
    """Floor all investments to whole euros; assign leftover cents to the largest buy."""
    import math

    result = {ticker: 0.0 for ticker in investments}
    total_floored = 0.0
    for ticker, amount in investments.items():
        if amount > 0:
            floored = float(math.floor(amount))
            result[ticker] = floored
            total_floored += floored

    remainder = round(total_budget - total_floored, 2)
    if remainder > 0 and any(v > 0 for v in result.values()):
        dump_ticker = max(result, key=result.get)
        result[dump_ticker] = round(result[dump_ticker] + remainder, 2)

    return result


def distribute_leftover_to_invested_etfs(
    buys: Dict[str, float],
    leftover: float,
) -> Dict[str, float]:
    """Split leftover cash proportionally across ETFs that received a buy."""
    if leftover <= 0:
        return buys
    result = dict(buys)
    additions = sell_proportionally(result, leftover)
    if not additions:
        return result
    for ticker, amount in additions.items():
        result[ticker] = round(result.get(ticker, 0.0) + amount, 2)
    return result


def calculate_investor_age(birth_date_str: str) -> int:
    try:
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
        today = date.today()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
    except (ValueError, TypeError):
        return 34


RETIRED_TICKERS = {"YCSH.DE", "PRAB.DE", "IBTE.UK"}
EXCLUDED_GD_TICKERS = RETIRED_TICKERS | REMOVED_GD_TICKERS


TOLERANCE_PP = {
    "SPYL.DE": 5.0,
    "IXUA.DE": 5.0,
    "VFEA.DE": 3.0,
    "EGLN.UK": 2.0,
}


def normalize_portfolio_type(portfolio_type: str) -> str:
    p = str(portfolio_type).strip()
    if p in LEGACY_GROWTH_PORTFOLIO_TYPES:
        return PORTFOLIO_TYPE_GROWTH
    return p


def migrate_growth_portfolio_metadata(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize legacy Growth portfolio names and types in loaded sheet data."""
    if df is None or df.empty:
        return df
    out = df.copy()
    if "portfolio_type" in out.columns:
        out["portfolio_type"] = out["portfolio_type"].apply(normalize_portfolio_type)
    if "portfolio_name" in out.columns:
        out["portfolio_name"] = (
            out["portfolio_name"]
            .astype(str)
            .str.replace(LEGACY_GROWTH_PORTFOLIO_NAME, PORTFOLIO_TYPE_GROWTH, regex=False)
        )
    return out


def get_tolerance_for_ticker(
    ticker: str,
    targets: Optional[Dict[str, float]] = None,
) -> float:
    ticker = str(ticker).upper()
    if ticker == "EGNL.UK":
        ticker = "EGLN.UK"
    return TOLERANCE_PP.get(ticker, 2.0)


def build_tolerance_map(targets: Dict[str, float]) -> Dict[str, float]:
    return {ticker: get_tolerance_for_ticker(ticker, targets) for ticker in targets}


def filter_growth_dividends_stocks(stocks):
    return [
        s for s in stocks
        if str(s.get("name", "")).upper() not in EXCLUDED_GD_TICKERS
    ]


def get_portfolio_safe_liquidity(portfolio_name: str) -> float:
    try:
        return float(st.session_state.get(f"{portfolio_name}_safe_liquidity", 0.0))
    except (ValueError, TypeError):
        return 0.0


def set_portfolio_safe_liquidity(portfolio_name: str, amount: float) -> None:
    st.session_state[f"{portfolio_name}_safe_liquidity"] = round(float(amount), 2)


def get_portfolio_uninvested_cash(portfolio_name: str) -> float:
    try:
        return max(0.0, float(st.session_state.get(f"{portfolio_name}_uninvested_cash", 0.0)))
    except (ValueError, TypeError):
        return 0.0


def get_portfolio_uninvested_reinvested(portfolio_name: str) -> float:
    try:
        return max(
            0.0,
            float(st.session_state.get(f"{portfolio_name}_uninvested_reinvested", 0.0)),
        )
    except (ValueError, TypeError):
        return 0.0


def set_portfolio_uninvested_reinvested(portfolio_name: str, amount: float) -> None:
    st.session_state[f"{portfolio_name}_uninvested_reinvested"] = round(float(amount), 2)


def contribution_with_uninvested(portfolio_name: str, base_contribution: float) -> float:
    return round(float(base_contribution) + get_portfolio_uninvested_cash(portfolio_name), 2)


def get_portfolio_monthly_contribution_setting(portfolio_name: str) -> float:
    try:
        return max(0.0, float(st.session_state.get(f"{portfolio_name}_monthly_invest", BASE_CONTRIBUTION)))
    except (ValueError, TypeError):
        return BASE_CONTRIBUTION


def growth_monthly_base_contribution(portfolio_name: str, month: int) -> float:
    """User-defined monthly amount; doubled in June and December."""
    base = get_portfolio_monthly_contribution_setting(portfolio_name)
    if month in (6, 12):
        return round(base * 2, 2)
    return round(base, 2)


def load_investment_log(conn, force_reload: bool = False) -> pd.DataFrame:
    if force_reload and "investment_log" in st.session_state:
        del st.session_state.investment_log
    if "investment_log" not in st.session_state:
        try:
            st.session_state.investment_log = conn.read(worksheet="InvestmentLog", ttl=0)
        except Exception:
            st.session_state.investment_log = pd.DataFrame()
    log = st.session_state.investment_log
    return log if log is not None else pd.DataFrame()


def get_total_invested(
    username: str,
    portfolio_name: str,
    conn,
) -> float:
    """
    Logged investments minus:
    - uninvested cash still on hold (already embedded in a prior log's total), and
    - uninvested rolled into this month's allocation (counted again in this log).
    """
    log = load_investment_log(conn)
    if log.empty or "Investment" not in log.columns:
        logged_sum = 0.0
    else:
        mask = (
            (log["username"].astype(str) == str(username))
            & (log["portfolio_name"].astype(str) == str(portfolio_name))
        )
        subset = log.loc[mask]
        logged_sum = (
            float(pd.to_numeric(subset["Investment"], errors="coerce").fillna(0).sum())
            if not subset.empty
            else 0.0
        )
    pending_uninvested = get_portfolio_uninvested_cash(portfolio_name)
    reinvested_uninvested = get_portfolio_uninvested_reinvested(portfolio_name)
    return round(
        max(0.0, logged_sum - pending_uninvested - reinvested_uninvested),
        2,
    )


def build_monthly_value_invested_series(
    username: str,
    portfolio_name: str,
    conn,
    current_total_value: Optional[float] = None,
    current_total_invested: Optional[float] = None,
) -> pd.DataFrame:
    """Monthly portfolio value before each month's allocation and cumulative total invested."""
    log = load_investment_log(conn)
    if log.empty or "timestamp" not in log.columns:
        months_data: list[dict] = []
    else:
        mask = (
            (log["username"].astype(str) == str(username))
            & (log["portfolio_name"].astype(str) == str(portfolio_name))
        )
        subset = log.loc[mask].copy()
        months_data = []
        if not subset.empty:
            subset["ts"] = pd.to_datetime(subset["timestamp"], errors="coerce")
            subset = subset.dropna(subset=["ts"])
            if not subset.empty:
                subset["month_key"] = subset["ts"].dt.to_period("M")
                for month_key, month_df in subset.groupby("month_key", sort=True):
                    month_invested = float(
                        pd.to_numeric(month_df["Investment"], errors="coerce")
                        .fillna(0)
                        .sum()
                    )
                    last_ts = month_df["ts"].max()
                    snapshot = month_df[month_df["ts"] == last_ts]
                    if "Current Value" in snapshot.columns:
                        total_value = float(
                            pd.to_numeric(snapshot["Current Value"], errors="coerce")
                            .fillna(0)
                            .sum()
                        )
                    elif "New Value" in snapshot.columns:
                        total_value = float(
                            pd.to_numeric(snapshot["New Value"], errors="coerce")
                            .fillna(0)
                            .sum()
                        ) - month_invested
                    else:
                        total_value = 0.0
                    months_data.append(
                        {
                            "month": month_key.to_timestamp(),
                            "total_value": round(total_value, 2),
                            "month_invested": round(month_invested, 2),
                        }
                    )

    if not months_data and current_total_value is None:
        return pd.DataFrame(columns=["month", "total_value", "total_invested"])

    df_series = pd.DataFrame(months_data)
    if not df_series.empty:
        df_series["total_invested"] = df_series["month_invested"].cumsum().round(2)
        df_series = df_series.drop(columns=["month_invested"])
        df_series["month"] = pd.to_datetime(df_series["month"])

    now = pd.Timestamp.now().to_period("M").to_timestamp()
    if current_total_value is not None or current_total_invested is not None:
        if df_series.empty or df_series["month"].max().to_period("M") != now.to_period("M"):
            row = {"month": now}
            if current_total_value is not None:
                row["total_value"] = round(float(current_total_value), 2)
            if current_total_invested is not None:
                row["total_invested"] = round(float(current_total_invested), 2)
                if current_total_value is None and not df_series.empty:
                    row["total_value"] = float(df_series["total_value"].iloc[-1])
            df_series = pd.concat([df_series, pd.DataFrame([row])], ignore_index=True)
        else:
            if current_total_value is not None:
                df_series.loc[df_series.index[-1], "total_value"] = round(
                    float(current_total_value), 2
                )
            if current_total_invested is not None:
                df_series.loc[df_series.index[-1], "total_invested"] = round(
                    float(current_total_invested), 2
                )

    if not df_series.empty:
        df_series["month_label"] = df_series["month"].dt.strftime("%b %Y")
    return df_series


def add_invested_line_with_gradient_fill(
    fig: go.Figure,
    x,
    y,
    *,
    line_color: str = "#24A16F",
    name: str = "Total Invested",
    hovertemplate: str = "Total Invested: %{y:.2f}<extra></extra>",
    n_bands: int = 24,
) -> None:
    """Area under the line with a vertical fade (works without plotly fillgradient)."""
    x_list = list(x)
    y_vals = [float(v) for v in y]
    for band in range(n_bands):
        frac_lo = band / n_bands
        frac_hi = (band + 1) / n_bands
        y_lo = [v * frac_lo for v in y_vals]
        y_hi = [v * frac_hi for v in y_vals]
        alpha = 0.5 * (band + 1) / n_bands
        fig.add_trace(
            go.Scatter(
                x=x_list + x_list[::-1],
                y=y_hi + y_lo[::-1],
                fill="toself",
                fillcolor=f"rgba(36, 161, 111, {alpha:.3f})",
                line=dict(width=0, color="rgba(0,0,0,0)"),
                mode="none",
                showlegend=False,
                hoverinfo="skip",
            )
        )
    fig.add_trace(
        go.Scatter(
            x=x_list,
            y=y_vals,
            mode="lines+markers",
            name=name,
            line=dict(color=line_color, width=2),
            marker=dict(size=7, color=line_color),
            hovertemplate=hovertemplate,
        )
    )


def allocate_contribution(
    contribution: float,
    age: int,
    current_values: Dict[str, float],
    min_order_size: float = 5.0,
) -> Dict[str, Any]:
    """
    Allocate monthly contribution without sales.
    Splits cash via cash_split(age); invests the rest in ETFs.
    Priority: (1) fill assets below min tolerance band, (2) proportional to
    remaining deficit vs target. Whole euros + cents to largest buy.
    """
    targets = growth_targets_by_ticker(age)
    all_assets = list(targets.keys())
    cash_fraction = cash_split(age)
    cash_part = round(contribution * cash_fraction, 2)
    invest_part = round(contribution - cash_part, 2)

    portfolio_value = sum(current_values.get(asset, 0.0) for asset in all_assets)
    new_total_value = portfolio_value + contribution

    tolerances = build_tolerance_map(targets)

    if portfolio_value <= 0:
        current_weights = {asset: 0.0 for asset in all_assets}
    else:
        current_weights = {
            asset: current_values.get(asset, 0.0) / portfolio_value * 100.0
            for asset in all_assets
        }

    deficits = {
        asset: targets[asset] - current_weights[asset]
        for asset in all_assets
    }

    raw_buys = {asset: 0.0 for asset in all_assets}
    remaining = invest_part
    below_min_band_assets = []

    if invest_part > 0:
        band_needs: Dict[str, float] = {}
        for asset in all_assets:
            min_band_pct = targets[asset] - tolerances[asset]
            if current_weights[asset] < min_band_pct:
                below_min_band_assets.append(asset)
                min_band_value = new_total_value * min_band_pct / 100.0
                band_needs[asset] = max(
                    0.0,
                    min_band_value - current_values.get(asset, 0.0),
                )

        total_band_need = sum(band_needs.values())
        if total_band_need > 0 and remaining > 0:
            if total_band_need <= remaining:
                for asset, need in band_needs.items():
                    raw_buys[asset] += need
                    remaining -= need
            else:
                for asset, need in band_needs.items():
                    share = (need / total_band_need) * remaining
                    raw_buys[asset] += share
                remaining = 0.0

        if remaining > 0:
            gap_remaining = {
                asset: max(
                    0.0,
                    new_total_value * targets[asset] / 100.0
                    - current_values.get(asset, 0.0)
                    - raw_buys[asset],
                )
                for asset in all_assets
                if deficits[asset] > 0
            }
            total_gap = sum(gap_remaining.values())
            if total_gap > 0:
                for asset, gap in gap_remaining.items():
                    raw_buys[asset] += remaining * gap / total_gap
            else:
                target_sum = sum(targets.values())
                for asset in all_assets:
                    raw_buys[asset] += remaining * targets[asset] / target_sum

    for asset in raw_buys:
        if raw_buys[asset] < min_order_size:
            raw_buys[asset] = 0.0

    rounded_buys = apply_cents_to_largest_investment(raw_buys, invest_part)
    invested_total = sum(rounded_buys.values())
    leftover_cash = round(max(0.0, invest_part - invested_total), 2)
    if leftover_cash > 0:
        rounded_buys = distribute_leftover_to_invested_etfs(rounded_buys, leftover_cash)
        invested_total = sum(rounded_buys.values())
        leftover_cash = round(max(0.0, invest_part - invested_total), 2)
        if leftover_cash > 0 and any(v > 0 for v in rounded_buys.values()):
            dump_ticker = max(
                (k for k, v in rounded_buys.items() if v > 0),
                key=lambda k: rounded_buys[k],
            )
            rounded_buys[dump_ticker] = round(rounded_buys[dump_ticker] + leftover_cash, 2)
            leftover_cash = 0.0

    return {
        "portfolio_value_before": round(portfolio_value, 2),
        "monthly_contribution": round(contribution, 2),
        "portfolio_value_after": round(new_total_value, 2),
        "portfolio_targets": round_weights(targets, 2),
        "current_weights": round_weights(current_weights, 2),
        "deficits": round_weights(deficits, 2),
        "tolerances": round_weights(tolerances, 2),
        "below_min_band": below_min_band_assets,
        "cash_part": cash_part,
        "cash_split": cash_fraction,
        "invest_part": invest_part,
        "raw_buys": round_weights(raw_buys, 2),
        "buys": round_weights(rounded_buys, 2),
        "leftover_cash": round(leftover_cash, 2),
        "is_retired": age >= RETIREMENT_AGE,
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

    /* Sidebar — compact layout (less scroll) */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.3rem !important;
    }
    [data-testid="stSidebar"] [data-testid="stElementContainer"] {
        margin-bottom: 0.1rem !important;
    }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        margin-bottom: 0.05rem !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stSidebar"] .stDateInput,
    [data-testid="stSidebar"] .stNumberInput {
        margin-bottom: 0.1rem !important;
    }
    [data-testid="stSidebar"] hr {
        display: none !important;
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

    /* Space between Total Value and portfolio buttons */
    [data-testid="stSidebar"] .sidebar-total-value {
        margin-bottom: 1.35rem !important;
        display: block !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_0"] {
        margin-top: 0.5rem !important;
    }

    /* Portfolio navigation buttons — contrast for text & emojis */
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] [data-testid="stButton"] {
        width: 100% !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] [data-testid="stButton"] > div {
        width: 100% !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        background-color: #FFFFFF !important;
        color: #111827 !important;
        border: 1px solid #94A3B8 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        line-height: 1.2 !important;
        min-height: 2.35rem !important;
        padding: 0.35rem 0.55rem !important;
        margin-bottom: 0.12rem !important;
        text-align: center !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08) !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button > div {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
        margin: 0 auto !important;
        padding: 0 !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button p {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 0.4rem !important;
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
        text-align: center !important;
        line-height: 1.2 !important;
        color: #111827 !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button span,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button div:not(:first-child) {
        color: #111827 !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button:hover {
        background-color: #E2E8F0 !important;
        border-color: #64748B !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-primary"] {
        background-color: #1E3A5F !important;
        border-color: #1E3A5F !important;
        color: #F8FAFC !important;
        box-shadow: 0 2px 6px rgba(30, 58, 95, 0.35) !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"] p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-primary"] p {
        color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"] span,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-primary"] span {
        color: #F8FAFC !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-primary"]:hover {
        background-color: #2D4A6F !important;
        border-color: #2D4A6F !important;
    }

    /* Other sidebar buttons — readable text on secondary style */
    [data-testid="stSidebar"] .stButton button[kind="secondary"] p,
    [data-testid="stSidebar"] .stButton button[kind="secondary"] span,
    [data-testid="stSidebar"] .stButton button[data-testid="baseButton-secondary"] p,
    [data-testid="stSidebar"] .stButton button[data-testid="baseButton-secondary"] span {
        color: var(--text-sidebar) !important;
    }
    [data-testid="stSidebar"] .stButton button[kind="primary"] p,
    [data-testid="stSidebar"] .stButton button[kind="primary"] span,
    [data-testid="stSidebar"] .stButton button[data-testid="baseButton-primary"] p,
    [data-testid="stSidebar"] .stButton button[data-testid="baseButton-primary"] span {
        color: #FFFFFF !important;
    }

    /* Sidebar — emerald buttons (logout, etc.; portfolio nav overrides below) */
    [data-testid="stSidebar"] div.stButton > button,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button {
        background-color: var(--primary-accent) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] div.stButton > button:hover,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
        background-color: var(--primary-hover) !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3) !important;
    }
    [data-testid="stSidebar"] div.stButton > button p,
    [data-testid="stSidebar"] div.stButton > button span,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button p,
    [data-testid="stSidebar"] div[data-testid="stButton"] > button span {
        color: #FFFFFF !important;
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
        padding: 16px 18px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        border: 1px solid rgba(255,255,255,0.05);
        text-align: left;
        margin-bottom: 0 !important;
        min-height: 6.25rem;
        height: 100%;
        width: 100%;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    [data-testid="stHorizontalBlock"]:has(.kpi-card) {
        align-items: stretch !important;
        margin-bottom: 0.65rem !important;
    }
    [data-testid="stHorizontalBlock"]:has(.kpi-card) > div[data-testid="column"] {
        display: flex !important;
        flex-direction: column !important;
    }
    .kpi-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94A3B8;
        margin-bottom: 6px;
        font-weight: 600;
        line-height: 1.2;
    }
    .kpi-value {
        font-size: 1.45rem;
        font-weight: 800;
        color: var(--text-light);
        line-height: 1.25;
        word-break: break-word;
    }
    .kpi-value-stack .kpi-value {
        font-size: 1.45rem;
        margin-bottom: 2px;
    }
    .kpi-subvalue {
        font-size: 1.05rem;
        font-weight: 700;
        line-height: 1.2;
    }
    /* Main content buttons (Emerald) — excludes sidebar portfolio nav */
    [data-testid="stMain"] div.stButton > button,
    [data-testid="stMain"] div[data-testid="stButton"] > button {
        background-color: var(--primary-accent) !important;
        color: #FFFFFF !important;
        border-radius: 10px;
        border: none !important;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    [data-testid="stMain"] div.stButton > button:hover,
    [data-testid="stMain"] div[data-testid="stButton"] > button:hover {
        background-color: var(--primary-hover) !important;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
    }
    [data-testid="stMain"] div.stButton > button p,
    [data-testid="stMain"] div.stButton > button span,
    [data-testid="stMain"] div[data-testid="stButton"] > button p,
    [data-testid="stMain"] div[data-testid="stButton"] > button span {
        color: #FFFFFF !important;
    }

    /* Manage purchases — delete: ghost button, red trash icon */
    [data-testid="stMain"] [class*="st-key-delete_unit_"] button,
    [data-testid="stMain"] [class*="st-key-delete_selected_"] button,
    [data-testid="stMain"] [class*="st-key-stock_delete_selected_"] button,
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stButton"] button {
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: #DC2626 !important;
        padding: 0.25rem 0.5rem !important;
    }
    [data-testid="stMain"] [class*="st-key-delete_unit_"] button:hover,
    [data-testid="stMain"] [class*="st-key-delete_selected_"] button:hover,
    [data-testid="stMain"] [class*="st-key-stock_delete_selected_"] button:hover,
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stButton"] button:hover {
        background-color: rgba(220, 38, 38, 0.12) !important;
        border: none !important;
        box-shadow: none !important;
    }
    [data-testid="stMain"] [class*="st-key-delete_unit_"] button svg,
    [data-testid="stMain"] [class*="st-key-delete_selected_"] button svg,
    [data-testid="stMain"] [class*="st-key-stock_delete_selected_"] button svg,
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stButton"] button svg {
        fill: #DC2626 !important;
        color: #DC2626 !important;
    }
    [data-testid="stMain"] [class*="st-key-delete_selected_"] button p,
    [data-testid="stMain"] [class*="st-key-delete_selected_"] button span,
    [data-testid="stMain"] [class*="st-key-stock_delete_selected_"] button p,
    [data-testid="stMain"] [class*="st-key-stock_delete_selected_"] button span {
        color: var(--text-light) !important;
    }

    /* Manage purchases — unit row alignment (checkbox + text + delete) */
    [data-testid="stMain"] [data-testid="stExpander"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] [data-testid="stHorizontalBlock"],
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stHorizontalBlock"],
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="column"] {
        align-items: center !important;
    }
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stMarkdown"],
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stMarkdownContainer"] {
        display: flex !important;
        align-items: center !important;
        margin: 0 !important;
        padding: 0 !important;
        min-height: 2.5rem !important;
    }
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stMarkdown"] p,
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.35 !important;
    }
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stCheckbox"] {
        margin: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stButton"] {
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
    }
    [data-testid="stMain"] [class*="st-key-stock_unit_row_"] [data-testid="stButton"] button {
        min-height: 2.25rem !important;
        padding: 0.25rem 0.65rem !important;
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

    /* Sidebar portfolio nav — reinstate inactive (white) vs active (navy) */
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="secondary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-secondary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="stBaseButton-secondary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="secondary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[data-testid="baseButton-secondary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[data-testid="stBaseButton-secondary"] {
        background-color: #FFFFFF !important;
        color: #111827 !important;
        border: 1px solid #94A3B8 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08) !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="secondary"] p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="secondary"] span,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="secondary"] p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="secondary"] span {
        color: #111827 !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-primary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="stBaseButton-primary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="primary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[data-testid="baseButton-primary"],
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[data-testid="stBaseButton-primary"] {
        background-color: #1E3A5F !important;
        border-color: #1E3A5F !important;
        color: #F8FAFC !important;
        box-shadow: 0 2px 6px rgba(30, 58, 95, 0.35) !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"] p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"] span,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="primary"] p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="primary"] span {
        color: #F8FAFC !important;
    }
    /* Portfolio nav hover — override sidebar emerald hover */
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] [data-testid="stButton"] button:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] [data-testid="stButton"] button:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="secondary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="secondary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[data-testid="baseButton-secondary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-secondary"]:hover {
        background-color: #E2E8F0 !important;
        border: 1px solid #94A3B8 !important;
        border-color: #64748B !important;
        color: #111827 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12) !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="secondary"]:hover p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="secondary"]:hover p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="secondary"]:hover span,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="secondary"]:hover span {
        color: #111827 !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[data-testid="baseButton-primary"]:hover,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[data-testid="baseButton-primary"]:hover {
        background-color: #2D4A6F !important;
        border-color: #2D4A6F !important;
        color: #F8FAFC !important;
        box-shadow: 0 2px 6px rgba(30, 58, 95, 0.35) !important;
    }
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="primary"]:hover p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"]:hover p,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_group"] button[kind="primary"]:hover span,
    [data-testid="stSidebar"] [class*="st-key-portfolio_nav_"] button[kind="primary"]:hover span {
        color: #F8FAFC !important;
    }

    /* Profit color overrides with extreme specificity placed at the very bottom */
    [data-testid="stAppViewContainer"] div.kpi-card .profit-green,
    [data-testid="stAppViewContainer"] span.profit-green {
        color: #10B981 !important;
        font-weight: 800 !important;
    }
    [data-testid="stAppViewContainer"] div.kpi-card .profit-red,
    [data-testid="stAppViewContainer"] span.profit-red {
        color: #EF4444 !important;
        font-weight: 800 !important;
    }

</style>
""", unsafe_allow_html=True)

def render_kpi_card(label: str, value: str, *, value_html: bool = False) -> None:
    value_block = value if value_html else f'<div class="kpi-value">{value}</div>'
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            {value_block}
        </div>
        """,
        unsafe_allow_html=True,
    )

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

def infer_country_and_currency_from_ticker(ticker: str) -> tuple[str, str]:
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


def stock_purchases_session_key(portfolio_name: str) -> str:
    return f"{portfolio_name}_stock_purchases"


def stock_market_overrides_key(portfolio_name: str) -> str:
    return f"{portfolio_name}_stock_market_overrides"


def load_stock_purchases_sheet(conn, force_reload: bool = False) -> pd.DataFrame:
    if force_reload and "stock_purchases_sheet" in st.session_state:
        del st.session_state.stock_purchases_sheet
    if "stock_purchases_sheet" not in st.session_state:
        try:
            st.session_state.stock_purchases_sheet = conn.read(
                worksheet="StockPurchases", ttl=0
            )
        except Exception:
            st.session_state.stock_purchases_sheet = pd.DataFrame()
    df = st.session_state.stock_purchases_sheet
    return df if df is not None else pd.DataFrame()


def purchase_dividend_yield(purchase: dict) -> float:
    """Yield % at purchase; falls back to dps / unit_price for older rows."""
    stored = float(purchase.get("dividend_yield", 0.0) or 0.0)
    if stored > 0:
        return stored
    unit_price = float(purchase.get("unit_price", 0.0) or 0.0)
    dps = float(purchase.get("dps", 0.0) or 0.0)
    if unit_price > 0 and dps > 0:
        return dps / unit_price * 100.0
    return 0.0


def purchase_dps(purchase: dict) -> float:
    """Annual dividend per share derived from yield % and purchase price."""
    unit_price = float(purchase.get("unit_price", 0.0) or 0.0)
    if unit_price <= 0:
        return 0.0
    return purchase_dividend_yield(purchase) / 100.0 * unit_price


def purchases_from_dataframe(df: pd.DataFrame) -> List[dict]:
    purchases = []
    if df is None or df.empty:
        return purchases
    for _, row in df.iterrows():
        ticker = str(row.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        purchases.append(
            {
                "id": str(row.get("purchase_id", uuid4())),
                "ticker": ticker,
                "name": str(row.get("stock_name", "") or ticker),
                "sector": str(row.get("sector", "") or ""),
                "industry": str(row.get("industry", "") or ""),
                "country": str(row.get("country", "") or ""),
                "currency": str(row.get("currency", "") or ""),
                "unit_price": float(row.get("unit_price", 0.0) or 0.0),
                "quantity": float(row.get("quantity", 0.0) or 0.0),
                "dividend_yield": float(row.get("dividend_yield", 0.0) or 0.0),
                "dps": float(row.get("dps", 0.0) or 0.0),
            }
        )
    return purchases


def migrate_stocks_to_purchases(stocks: List[dict]) -> List[dict]:
    purchases = []
    for stock in stocks:
        ticker = str(stock.get("name", "")).strip().upper()
        if not ticker or ticker == "__PLACEHOLDER__":
            continue
        qty = float(stock.get("quantity", 0.0) or 0.0)
        avg = float(stock.get("average_price", 0.0) or 0.0)
        invested = float(stock.get("current_price", 0.0) or 0.0)
        unit_price = avg if avg > 0 else (invested / qty if qty > 0 else 0.0)
        country = stock.get("country", "") or ""
        currency = stock.get("currency", "") or ""
        if not country or not currency:
            country, currency = infer_country_and_currency_from_ticker(ticker)
        div_yield = float(stock.get("dividend_yield", 0.0) or 0.0)
        purchases.append(
            {
                "id": str(uuid4()),
                "ticker": ticker,
                "name": stock.get("full_name", "") or ticker,
                "sector": stock.get("sector", "") or "",
                "industry": stock.get("industry", "") or "",
                "country": country,
                "currency": currency,
                "unit_price": round(unit_price, 4),
                "quantity": round(qty, 4),
                "dividend_yield": round(div_yield, 2),
                "dps": round((div_yield / 100.0) * unit_price, 4) if unit_price > 0 else 0.0,
            }
        )
    return purchases


def aggregate_stock_purchases(
    purchases: List[dict],
    dividend_map: Dict[str, float],
    market_overrides: Dict[str, float],
) -> List[dict]:
    buckets: Dict[str, dict] = {}
    for purchase in purchases:
        ticker = str(purchase.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        qty = float(purchase.get("quantity", 0.0) or 0.0)
        unit_price = float(purchase.get("unit_price", 0.0) or 0.0)
        invested = unit_price * qty
        dps = purchase_dps(purchase)

        if ticker not in buckets:
            buckets[ticker] = {
                "ticker": ticker,
                "name": purchase.get("name", ticker),
                "sector": purchase.get("sector", ""),
                "industry": purchase.get("industry", ""),
                "country": purchase.get("country", ""),
                "currency": purchase.get("currency", ""),
                "quantity": 0.0,
                "invested_value": 0.0,
                "dps_qty_sum": 0.0,
                "lowest_price": unit_price if unit_price > 0 else None,
            }
        bucket = buckets[ticker]
        bucket["quantity"] += qty
        bucket["invested_value"] += invested
        bucket["dps_qty_sum"] += dps * qty
        if unit_price > 0:
            if bucket["lowest_price"] is None or unit_price < bucket["lowest_price"]:
                bucket["lowest_price"] = unit_price

    summaries = []
    for ticker, bucket in sorted(buckets.items()):
        qty = bucket["quantity"]
        invested = bucket["invested_value"]
        avg_price = invested / qty if qty > 0 else 0.0
        lowest = bucket["lowest_price"] if bucket["lowest_price"] is not None else 0.0
        market_value = float(market_overrides.get(ticker, invested))
        price_per_share = market_value / qty if qty > 0 else 0.0
        weighted_dps = bucket["dps_qty_sum"] / qty if qty > 0 else 0.0
        div_yield = (weighted_dps / price_per_share * 100.0) if price_per_share > 0 else 0.0
        yoc = (div_yield / 100.0) * (market_value / invested) * 100.0 if invested > 0 else 0.0
        divs_received = float(dividend_map.get(ticker, 0.0))
        received_yoc = (divs_received / invested * 100.0) if invested > 0 else 0.0

        summaries.append(
            {
                "ticker": ticker,
                "name": bucket["name"],
                "quantity": round(qty, 4),
                "invested_value": round(invested, 2),
                "avg_price": round(avg_price, 4),
                "lowest_price": round(lowest, 4),
                "market_value": round(market_value, 2),
                "div_yield": round(div_yield, 2),
                "yoc": round(yoc, 2),
                "received_yoc": round(received_yoc, 2),
                "above_avg_15": round(avg_price * 1.15, 4),
                "below_lowest_10": round(lowest * 0.90, 4),
                "sector": bucket["sector"],
                "industry": bucket["industry"],
                "country": bucket["country"],
                "currency": bucket["currency"],
            }
        )
    return summaries


def expand_purchases_to_units(purchases: List[dict]) -> List[dict]:
    """One UI row per whole share; fractional lots stay as a single row."""
    units: List[dict] = []
    for purchase in purchases:
        qty = float(purchase.get("quantity", 0.0) or 0.0)
        if qty <= 0:
            continue
        whole = int(round(qty))
        if abs(qty - whole) < 1e-6 and whole >= 1:
            for unit_index in range(whole):
                units.append(
                    {
                        "unit_key": f"{purchase['id']}#{unit_index}",
                        "purchase_id": purchase["id"],
                        "unit_index": unit_index,
                        "ticker": purchase["ticker"],
                        "price": float(purchase["unit_price"]),
                        "currency": purchase.get("currency", ""),
                        "dividend_yield": purchase_dividend_yield(purchase),
                        "fractional": False,
                    }
                )
        else:
            units.append(
                {
                    "unit_key": f"{purchase['id']}#frac",
                    "purchase_id": purchase["id"],
                    "unit_index": 0,
                    "ticker": purchase["ticker"],
                    "price": float(purchase["unit_price"]),
                    "currency": purchase.get("currency", ""),
                    "dividend_yield": purchase_dividend_yield(purchase),
                    "fractional": True,
                    "display_qty": qty,
                }
            )
    return units


def remove_purchase_unit(
    purchases: List[dict], purchase_id: str, unit_index: int
) -> List[dict]:
    updated: List[dict] = []
    for purchase in purchases:
        if str(purchase.get("id")) != str(purchase_id):
            updated.append(purchase)
            continue
        qty = float(purchase.get("quantity", 0.0) or 0.0)
        whole = int(round(qty))
        if abs(qty - whole) >= 1e-6 or whole < 1:
            continue
        new_qty = whole - 1
        if new_qty > 0:
            copy_p = purchase.copy()
            copy_p["quantity"] = float(new_qty)
            updated.append(copy_p)
    return updated


def remove_all_purchases_for_ticker(
    purchases: List[dict], ticker: str
) -> List[dict]:
    target = str(ticker).strip().upper()
    return [p for p in purchases if str(p.get("ticker", "")).upper() != target]


def stock_selected_units_key(portfolio_name: str) -> str:
    return f"{portfolio_name}_selected_purchase_units"


def unit_checkbox_key(portfolio_name: str, unit_key: str) -> str:
    return f"unit_sel_{portfolio_name}_{unit_key}"


def remove_selected_units(
    purchases: List[dict], unit_keys: set
) -> List[dict]:
    if not unit_keys:
        return purchases
    remaining = list(purchases)
    frac_ids = {
        key[: -len("#frac")]
        for key in unit_keys
        if str(key).endswith("#frac")
    }
    if frac_ids:
        remaining = [p for p in remaining if p.get("id") not in frac_ids]

    removals_by_purchase: Dict[str, int] = {}
    for key in unit_keys:
        key_str = str(key)
        if key_str.endswith("#frac"):
            continue
        purchase_id = key_str.rsplit("#", 1)[0]
        removals_by_purchase[purchase_id] = removals_by_purchase.get(purchase_id, 0) + 1

    for purchase_id, count in removals_by_purchase.items():
        for _ in range(count):
            remaining = remove_purchase_unit(remaining, purchase_id, 0)
    return remaining


def select_all_ticker_master_key(portfolio_name: str, ticker: str) -> str:
    return f"select_all_{portfolio_name}_{ticker}"


def manage_ticker_expander_key(portfolio_name: str, ticker: str) -> str:
    return f"manage_exp_{portfolio_name}_{ticker}"


def sync_unit_checkboxes_from_selection(
    portfolio_name: str, units: List[dict], selected_set: set
) -> None:
    for unit in units:
        unit_key = unit["unit_key"]
        st.session_state[unit_checkbox_key(portfolio_name, unit_key)] = (
            unit_key in selected_set
        )


def on_select_all_ticker_changed(
    portfolio_name: str, ticker: str, ticker_unit_keys: tuple
) -> None:
    selected_key = stock_selected_units_key(portfolio_name)
    master_key = select_all_ticker_master_key(portfolio_name, ticker)
    current = set(st.session_state.get(selected_key, set()))
    ticker_set = set(ticker_unit_keys)
    if st.session_state.get(master_key, False):
        current.update(ticker_set)
    else:
        current -= ticker_set
    st.session_state[selected_key] = current
    for unit_key in ticker_unit_keys:
        st.session_state[unit_checkbox_key(portfolio_name, unit_key)] = (
            unit_key in current
        )


def on_unit_selection_changed(
    portfolio_name: str,
    ticker: str,
    unit_key: str,
    ticker_unit_keys: tuple,
) -> None:
    selected_key = stock_selected_units_key(portfolio_name)
    cb_key = unit_checkbox_key(portfolio_name, unit_key)
    current = set(st.session_state.get(selected_key, set()))
    if st.session_state.get(cb_key, False):
        current.add(unit_key)
    else:
        current.discard(unit_key)
    st.session_state[selected_key] = current


def apply_purchases_update(
    portfolio_name: str, purchases: List[dict], *, clear_selection: bool = True
) -> None:
    st.session_state[stock_purchases_session_key(portfolio_name)] = purchases
    if clear_selection:
        st.session_state[stock_selected_units_key(portfolio_name)] = set()
        for key in list(st.session_state.keys()):
            if key.startswith(
                (
                    f"unit_sel_{portfolio_name}_",
                    f"select_all_{portfolio_name}_",
                    f"manage_exp_{portfolio_name}_",
                )
            ):
                del st.session_state[key]
    sync_stocks_from_purchases(portfolio_name, purchases)
    st.session_state.has_unsaved_changes = True
    st.rerun()


@st.fragment
def render_manage_stock_purchases_units(
    portfolio_name: str, purchases: List[dict]
) -> None:
    """Per-ticker unit list; fragment rerun keeps expanders open while selecting."""
    units = expand_purchases_to_units(purchases)
    selected_key = stock_selected_units_key(portfolio_name)
    if selected_key not in st.session_state:
        st.session_state[selected_key] = set()

    units_by_ticker: Dict[str, List[dict]] = {}
    for unit in units:
        units_by_ticker.setdefault(unit["ticker"], []).append(unit)

    selected_set = set(st.session_state.get(selected_key, set()))
    sync_unit_checkboxes_from_selection(portfolio_name, units, selected_set)

    for ticker in sorted(units_by_ticker.keys()):
        ticker_units = units_by_ticker[ticker]
        unit_count = len(ticker_units)
        ticker_unit_keys = tuple(u["unit_key"] for u in ticker_units)
        ticker_keys_set = set(ticker_unit_keys)
        master_key = select_all_ticker_master_key(portfolio_name, ticker)
        all_ticker_selected = (
            bool(ticker_keys_set) and ticker_keys_set <= selected_set
        )
        st.session_state[master_key] = all_ticker_selected

        with st.expander(
            f"{ticker} — {unit_count} unit"
            f"{'s' if unit_count != 1 else ''}",
        ):
            st.checkbox(
                "Select all",
                key=master_key,
                on_change=on_select_all_ticker_changed,
                args=(portfolio_name, ticker, ticker_unit_keys),
            )

            for unit in ticker_units:
                if unit.get("fractional"):
                    unit_label = f"Lot ×{unit['display_qty']:,.4f}"
                else:
                    unit_label = f"Unit {unit['unit_index'] + 1}"
                row_key = f"stock_unit_row_{portfolio_name}_{unit['unit_key']}"
                with st.container(key=row_key):
                    chk_col, info_col, del_col = st.columns(
                        [0.55, 9, 0.75],
                        gap="small",
                        vertical_alignment="center",
                    )
                    with chk_col:
                        st.checkbox(
                            " ",
                            key=unit_checkbox_key(portfolio_name, unit["unit_key"]),
                            on_change=on_unit_selection_changed,
                            args=(
                                portfolio_name,
                                ticker,
                                unit["unit_key"],
                                ticker_unit_keys,
                            ),
                            label_visibility="collapsed",
                        )
                    info_col.markdown(
                        f"**{unit_label}** — "
                        f"{unit['price']:,.2f} {unit.get('currency', '')}"
                    )
                    if del_col.button(
                        "",
                        icon=DELETE_ICON,
                        help="Remove this unit",
                        key=f"delete_unit_{portfolio_name}_{unit['unit_key']}",
                        type="tertiary",
                        width="content",
                    ):
                        if unit.get("fractional"):
                            remaining = [
                                p
                                for p in purchases
                                if p["id"] != unit["purchase_id"]
                            ]
                        else:
                            remaining = remove_purchase_unit(
                                purchases,
                                unit["purchase_id"],
                                unit["unit_index"],
                            )
                        apply_purchases_update(portfolio_name, remaining)

            ticker_selected_set = ticker_keys_set & set(
                st.session_state.get(selected_key, set())
            )
            if ticker_selected_set:
                with st.container(
                    key=f"stock_delete_selected_{portfolio_name}_{ticker}"
                ):
                    if st.button(
                        f"Delete selected ({len(ticker_selected_set)})",
                        icon=DELETE_ICON,
                        key=f"delete_selected_{portfolio_name}_{ticker}",
                        type="tertiary",
                        help="Delete selected units",
                    ):
                        apply_purchases_update(
                            portfolio_name,
                            remove_selected_units(purchases, ticker_selected_set),
                        )


def style_stocks_summary_for_editor(df: pd.DataFrame):
    """Styler for st.data_editor — colors apply to disabled columns only."""
    sell_css = "background-color: rgba(185, 28, 28, 0.55); color: #FEE2E2; font-weight: 600;"
    buy_css = "background-color: rgba(21, 128, 61, 0.55); color: #DCFCE7; font-weight: 600;"

    def _color_columns(col: pd.Series):
        if col.name == "Sell Price":
            return [buy_css] * len(col)
        if col.name == "Buy Price":
            return [sell_css] * len(col)
        return [""] * len(col)

    fmt = {
        "Current %": "{:.2f}%",
        "Market Value": "{:,.2f}",
        "Invested Value": "{:,.2f}",
        "Quantity": "{:,.0f}",
        "Avg. Price": "{:,.4f}",
        "Div. Yield (%)": "{:.2f}%",
        "YoC (%)": "{:.2f}%",
        "Received YoC (%)": "{:.2f}%",
        "Sell Price": "{:,.4f}",
        "Buy Price": "{:,.4f}",
    }
    return df.style.apply(_color_columns, axis=0).format(
        {k: v for k, v in fmt.items() if k in df.columns},
        na_rep="—",
    )


def sync_stocks_from_purchases(
    portfolio_name: str,
    purchases: List[dict],
    market_overrides: Optional[Dict[str, float]] = None,
) -> None:
    dividend_map: Dict[str, float] = {}
    df_divs = st.session_state.get("dividends", pd.DataFrame())
    username = st.session_state.get("username")
    if (
        username
        and not df_divs.empty
        and "ticker" in df_divs.columns
        and "amount" in df_divs.columns
    ):
        df_divs = df_divs.copy()
        df_divs["amount"] = pd.to_numeric(df_divs["amount"], errors="coerce").fillna(0.0)
        mask = (df_divs["username"] == username) & (
            df_divs["portfolio_name"] == portfolio_name
        )
        dividend_map = df_divs.loc[mask].groupby("ticker")["amount"].sum().to_dict()

    overrides = market_overrides or st.session_state.get(
        stock_market_overrides_key(portfolio_name), {}
    )
    summaries = aggregate_stock_purchases(purchases, dividend_map, overrides)
    existing = {s["name"]: s for s in st.session_state.get("stocks", [])}

    new_stocks = []
    for summary in summaries:
        ticker = summary["ticker"]
        prev = existing.get(ticker, {})
        new_stocks.append(
            {
                "name": ticker,
                "current_value": summary["market_value"],
                "current_price": summary["invested_value"],
                "target_allocation": float(prev.get("target_allocation", 0.0) or 0.0),
                "tolerance": float(prev.get("tolerance", 2.0) or 2.0),
                "expense_ratio": float(prev.get("expense_ratio", 0.0) or 0.0),
                "full_name": summary["name"],
                "sector": summary["sector"],
                "industry": summary["industry"],
                "country": summary["country"],
                "currency": summary["currency"],
                "quantity": summary["quantity"],
                "average_price": summary["avg_price"],
                "dividend_yield": summary["div_yield"],
            }
        )
    st.session_state.stocks = new_stocks


def persist_stock_purchases(
    conn,
    username: str,
    portfolio_name: str,
    purchases: List[dict],
) -> None:
    sheet = load_stock_purchases_sheet(conn)
    purchase_cols = [
        "username",
        "portfolio_name",
        "purchase_id",
        "ticker",
        "stock_name",
        "sector",
        "industry",
        "country",
        "currency",
        "unit_price",
        "quantity",
        "dividend_yield",
        "dps",
    ]
    if sheet.empty or "username" not in sheet.columns:
        sheet = pd.DataFrame(columns=purchase_cols)
        remaining = sheet
    else:
        mask = (sheet["username"].astype(str) == str(username)) & (
            sheet["portfolio_name"].astype(str) == str(portfolio_name)
        )
        remaining = sheet.loc[~mask]
    rows = []
    for purchase in purchases:
        rows.append(
            {
                "username": username,
                "portfolio_name": portfolio_name,
                "purchase_id": purchase["id"],
                "ticker": purchase["ticker"],
                "stock_name": purchase.get("name", purchase["ticker"]),
                "sector": purchase.get("sector", ""),
                "industry": purchase.get("industry", ""),
                "country": purchase.get("country", ""),
                "currency": purchase.get("currency", ""),
                "unit_price": float(purchase.get("unit_price", 0.0) or 0.0),
                "quantity": float(purchase.get("quantity", 0.0) or 0.0),
                "dividend_yield": purchase_dividend_yield(purchase),
                "dps": purchase_dps(purchase),
            }
        )
    new_rows = pd.DataFrame(rows) if rows else pd.DataFrame(columns=sheet.columns)
    updated = (
        pd.concat([remaining, new_rows], ignore_index=True)
        if not remaining.empty
        else new_rows
    )
    conn.update(worksheet="StockPurchases", data=updated)
    st.session_state.stock_purchases_sheet = updated
    load_stock_purchases_sheet(conn, force_reload=True)


@st.dialog("Add purchase")
def stocks_add_purchase_dialog(portfolio_name: str) -> None:
    st.caption("Purchase details are used to calculate the summary table.")
    ticker = st.text_input("Ticker", placeholder="e.g. INTC.US").strip().upper()
    sector = st.text_input("Sector")
    industry = st.text_input("Industry")
    country = st.text_input("Country")
    currency = st.text_input("Currency")
    unit_price = st.number_input("Price (per share)", min_value=0.0, step=0.01, format="%.4f")
    quantity = st.number_input("Quantity", min_value=0.0, step=0.0001, format="%.4f")
    dividend_yield = st.number_input(
        "Div. Yield (%)",
        min_value=0.0,
        max_value=100.0,
        step=0.01,
        format="%.2f",
    )

    col_cancel, col_save = st.columns(2)
    with col_cancel:
        if st.button("Cancel", width="stretch"):
            st.rerun()
    with col_save:
        if st.button("Save purchase", type="primary", width="stretch"):
            if not ticker:
                st.error("Ticker is required.")
                return
            if quantity <= 0:
                st.error("Quantity must be greater than zero.")
                return
            if unit_price <= 0:
                st.error("Price must be greater than zero.")
                return
            final_country = country.strip()
            final_currency = currency.strip()
            if not final_country or not final_currency:
                inf_country, inf_currency = infer_country_and_currency_from_ticker(
                    ticker
                )
                final_country = final_country or inf_country
                final_currency = final_currency or inf_currency
            purchases = list(
                st.session_state.get(stock_purchases_session_key(portfolio_name), [])
            )
            purchases.append(
                {
                    "id": str(uuid4()),
                    "ticker": ticker,
                    "name": ticker,
                    "sector": sector.strip(),
                    "industry": industry.strip(),
                    "country": final_country,
                    "currency": final_currency or "EUR",
                    "unit_price": round(float(unit_price), 4),
                    "quantity": round(float(quantity), 4),
                    "dividend_yield": round(float(dividend_yield), 2),
                    "dps": round(
                        float(dividend_yield) / 100.0 * float(unit_price), 4
                    ),
                }
            )
            st.session_state[stock_purchases_session_key(portfolio_name)] = purchases
            sync_stocks_from_purchases(portfolio_name, purchases)
            st.session_state.has_unsaved_changes = True
            st.rerun()


def reset_portfolio_state():
    clear_recommendations()
    selected = st.session_state.get("selected_portfolio")
    if selected:
        keys_to_clear = [k for k in st.session_state.keys() if k.startswith(f"{selected}_")]
        for k in keys_to_clear:
            del st.session_state[k]
    if "last_selected_portfolio" in st.session_state:
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
            
            required_columns = PORTFOLIOS_REQUIRED_COLUMNS

            if raw_data.empty:
                raw_data = empty_portfolios_dataframe()
            else:
                for col in required_columns:
                    if col not in raw_data.columns:
                        if col == 'portfolio_monthly_invest': raw_data[col] = 1000.0
                        elif col == 'portfolio_use_indicators': raw_data[col] = False
                        elif col == 'portfolio_buffett_index': raw_data[col] = 195.0
                        elif col == 'portfolio_type': raw_data[col] = 'Other'
                        elif col == 'portfolio_birth_date': raw_data[col] = ''
                        elif col == 'portfolio_uninvested_cash': raw_data[col] = 0.0
                        elif col == 'portfolio_safe_liquidity': raw_data[col] = 0.0
                        elif col == 'portfolio_uninvested_reinvested': raw_data[col] = 0.0
                        elif col == 'investor_birth_date': raw_data[col] = DEFAULT_INVESTOR_BIRTH_DATE
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
                raw_data = migrate_growth_portfolio_metadata(raw_data)

            st.session_state.master_data = raw_data

            for nav_key in ("selected_portfolio", "portfolio_selector", "last_selected_portfolio"):
                if st.session_state.get(nav_key) == LEGACY_GROWTH_PORTFOLIO_NAME:
                    st.session_state[nav_key] = PORTFOLIO_TYPE_GROWTH

            # Load Dividends Data
            if 'dividends' not in st.session_state:
                try:
                    div_data = conn.read(worksheet="Dividends", ttl=0)
                    if div_data is None or div_data.empty:
                        div_data = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])
                    else:
                        # Drop rows where 'date' is empty, NaN, NaT, or invalid
                        div_data = div_data.dropna(subset=['date'])
                        div_data = div_data[div_data['date'].astype(str).str.strip() != ""]
                        div_data = div_data[~div_data['date'].astype(str).str.strip().str.lower().isin(['nat', 'nan', 'none'])]
                    
                    # Ensure columns exist
                    for col in ['date', 'ticker', 'amount', 'portfolio_name', 'username']:
                        if col not in div_data.columns:
                            div_data[col] = '' if col in ['date', 'ticker', 'portfolio_name', 'username'] else 0.0
                    st.session_state.dividends = div_data
                except Exception:
                     # Worksheet likely doesn't exist yet
                    st.session_state.dividends = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])

        except Exception:
            st.session_state.master_data = empty_portfolios_dataframe()

    data = st.session_state.get("master_data", empty_portfolios_dataframe())
    if "portfolio_name" not in data.columns:
        data = empty_portfolios_dataframe()
        st.session_state.master_data = data

    with st.sidebar:
        # 1. Logout & Welcome
        authenticator.logout('Logout', 'main')
        st.write(f'Welcome *{name}*')
        
        # 1. Global Total Invested
        user_all_data = filter_master_data_for_user(data, username)
        
        global_total = 0.0
        merged_global = pd.DataFrame()
        
        if not user_all_data.empty:
            valid_data = user_all_data[user_all_data['stock_name'] != '__PLACEHOLDER__'].copy()
            
            global_valid_data = valid_data.copy()
            
            # Separate Gold, Growth, and Dividends based on user asset categories
            growth_tickers = {"SPYL.DE", "IXUA.DE", "VFEA.DE"}
            dividend_tickers = {"WTEQ.DE", "VDIV.DE", "EDP.PT", "JMT.PT"}
            gold_tickers = {"EGLN.UK", "EGNL.UK"}

            def assign_global_label(row):
                ticker = str(row['stock_name']).upper().strip()
                p_type = normalize_portfolio_type(str(row['portfolio_type']).strip())
                p_name = str(row['portfolio_name']).strip()

                if ticker in RETIRED_TICKERS:
                    return p_name
                
                if ticker in gold_tickers:
                    return "Gold"
                
                if p_type == "Kids":
                    return p_name

                # Split Growth (Unified Portfolio) assets
                if p_type == PORTFOLIO_TYPE_GROWTH or "growth" in p_name.lower():
                    if ticker in growth_tickers:
                        return "Growth"
                    if ticker in dividend_tickers:
                        return "Dividends"

                return p_name

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
            <div class="sidebar-total-value" style="padding-top: 4px; line-height: 1.15; margin-bottom: 1.35rem;">
                <div style="color: #1f2937; font-size: 1.45rem; font-weight: 800;">💶 Total Value</div>
                <div class="green-text-force" style="color: #10B981 !important; font-size: 1.85rem !important; font-weight: 900 !important; padding-left: 2rem; margin-top: -4px;">€{global_total:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # --- Data Filtering & Initialization (Top Level) ---

    # Determine existing portfolios
    if not user_all_data.empty:
        existing_portfolios = sorted(user_all_data['portfolio_name'].unique().tolist())
    else:
        existing_portfolios = []
    portfolio_options = [GLOBAL_OVERVIEW_LABEL] + existing_portfolios

    selected_portfolio = None
    if portfolio_options:
        if "selected_portfolio" not in st.session_state:
            st.session_state.selected_portfolio = portfolio_options[0]
        if "portfolio_selector" in st.session_state:
            legacy_sel = st.session_state.portfolio_selector
            if legacy_sel in portfolio_options:
                st.session_state.selected_portfolio = legacy_sel
            del st.session_state.portfolio_selector
        if "new_portfolio_created" in st.session_state:
            target_new = st.session_state.new_portfolio_created
            if target_new in portfolio_options:
                st.session_state.selected_portfolio = target_new
            del st.session_state.new_portfolio_created
        elif st.session_state.get("last_selected_portfolio") in portfolio_options:
            st.session_state.selected_portfolio = st.session_state.last_selected_portfolio

        selected_portfolio = st.session_state.selected_portfolio
        if selected_portfolio not in portfolio_options:
            st.session_state.selected_portfolio = portfolio_options[0]
            selected_portfolio = portfolio_options[0]

    def format_portfolio_nav_label(p_name: str) -> str:
        if p_name == GLOBAL_OVERVIEW_LABEL:
            return "🌍\u00a0Global Overview"
        display_name = str(p_name).replace(
            LEGACY_GROWTH_PORTFOLIO_NAME, PORTFOLIO_TYPE_GROWTH
        )
        name_lower = display_name.lower()
        if "grow" in name_lower or "accum" in name_lower:
            return f"🌱\u00a0{display_name}"
        if "dividend" in name_lower:
            return f"💸\u00a0{display_name}"

        if user_all_data.empty:
            return display_name
        p_rows = filter_master_data_by_portfolio(user_all_data, p_name)
        if p_rows.empty:
            return display_name
        p_type_label = p_rows["portfolio_type"].iloc[0]

        if p_type_label == "Stocks":
            return f"📈\u00a0{display_name}"
        if p_type_label == "Kids":
            return f"🧸\u00a0{display_name}"
        if p_type_label == PORTFOLIO_TYPE_GROWTH:
            return f"🏛️\u00a0{display_name}"
        return f"📁\u00a0{display_name}"

    # --- Sidebar UI ---
    with st.sidebar:
        if portfolio_options:
            with st.container(key="portfolio_nav_group"):
                for idx, p_name in enumerate(portfolio_options):
                    is_active = selected_portfolio == p_name
                    if st.button(
                        format_portfolio_nav_label(p_name),
                        key=f"portfolio_nav_{idx}",
                        width="stretch",
                        type="primary" if is_active else "secondary",
                    ):
                        if not is_active:
                            st.session_state.selected_portfolio = p_name
                            reset_portfolio_state()
                            st.rerun()
        else:
            selected_portfolio = None
            st.info("No portfolios found.")

    # --- Sync Data Logic (Source of Truth) ---
    # Load current stocks from Master data (Persistent state)
    # This list reflects the state AT THE START of the run.
    p_type = PORTFOLIO_TYPE_GROWTH
    if selected_portfolio and selected_portfolio != GLOBAL_OVERVIEW_LABEL:
        p_rows = filter_master_data_by_portfolio(user_all_data, selected_portfolio)
        if not p_rows.empty:
            p_type = normalize_portfolio_type(p_rows["portfolio_type"].iloc[0])

    user_portfolio_df = (
        filter_master_data_by_portfolio(user_all_data, selected_portfolio)
        if selected_portfolio and selected_portfolio != GLOBAL_OVERVIEW_LABEL
        else empty_portfolios_dataframe()
    )
    user_portfolio_df = user_portfolio_df[user_portfolio_df['stock_name'] != "__PLACEHOLDER__"] if not user_portfolio_df.empty else pd.DataFrame()
    
    # 2. Main Page Header & State Management Logic (Sync with DB) for consistent UI
    if not user_portfolio_df.empty:
        user_portfolio_df = user_portfolio_df.sort_values(by='target_allocation', ascending=False)
    
    # Initialize session state for stocks ONLY if portfolio changes or it's first run
    if st.session_state.get('last_selected_portfolio') != selected_portfolio:
        current_stocks = []
        if p_type == PORTFOLIO_TYPE_GROWTH:
            # Map tickers and aggregate duplicate holdings (e.g. from historical merges)
            ticker_map = {
                "EGNL.UK": "EGLN.UK",
                "EGLN.UK": "EGLN.UK",
            }
            aggregated_holdings = {}
            for _, row in user_portfolio_df.iterrows():
                raw_name = str(row['stock_name'])
                mapped_name = ticker_map.get(raw_name, raw_name)

                if mapped_name.upper() in EXCLUDED_GD_TICKERS:
                    continue
                
                if mapped_name not in aggregated_holdings:
                    aggregated_holdings[mapped_name] = {
                        "name": mapped_name,
                        "current_value": 0.0,
                        "target_allocation": 0.0,
                        "tolerance": get_tolerance_for_ticker(mapped_name),
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

            current_stocks = filter_growth_dividends_stocks(list(aggregated_holdings.values()))
            
            required_tickers = GROWTH_DIVIDENDS_TICKERS
            existing_tickers = [s["name"] for s in current_stocks]
            for ticker in required_tickers:
                if ticker not in existing_tickers:
                    current_stocks.append({
                        "name": ticker,
                        "current_value": 0.0,
                        "target_allocation": 0.0,
                        "tolerance": get_tolerance_for_ticker(ticker),
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

        if p_type == "Stocks" and selected_portfolio:
            purchases_sheet = load_stock_purchases_sheet(conn)
            if (
                not purchases_sheet.empty
                and "username" in purchases_sheet.columns
                and "portfolio_name" in purchases_sheet.columns
            ):
                pmask = (
                    (purchases_sheet["username"].astype(str) == str(username))
                    & (
                        purchases_sheet["portfolio_name"].astype(str)
                        == str(selected_portfolio)
                    )
                )
                purchases = purchases_from_dataframe(purchases_sheet.loc[pmask])
            else:
                purchases = []
            if not purchases:
                purchases = migrate_stocks_to_purchases(current_stocks)
            st.session_state[stock_purchases_session_key(selected_portfolio)] = purchases
            market_overrides = {
                str(s["name"]).upper(): float(s.get("current_value", 0.0) or 0.0)
                for s in current_stocks
                if s.get("name") and s["name"] != "__PLACEHOLDER__"
            }
            st.session_state[stock_market_overrides_key(selected_portfolio)] = (
                market_overrides
            )
            sync_stocks_from_purchases(
                selected_portfolio, purchases, market_overrides
            )

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
                try:
                    st.session_state[f"{selected_portfolio}_safe_liquidity"] = float(
                        first_row.get('portfolio_safe_liquidity', 0.0)
                    )
                except (ValueError, TypeError):
                    st.session_state[f"{selected_portfolio}_safe_liquidity"] = 0.0
                try:
                    st.session_state[f"{selected_portfolio}_uninvested_reinvested"] = float(
                        first_row.get('portfolio_uninvested_reinvested', 0.0)
                    )
                except (ValueError, TypeError):
                    st.session_state[f"{selected_portfolio}_uninvested_reinvested"] = 0.0

                st.session_state[f"{selected_portfolio}_investor_birth_date"] = DEFAULT_INVESTOR_BIRTH_DATE
                
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

        # 3. Growth Targets and Tolerances Overrides
        if p_type == PORTFOLIO_TYPE_GROWTH:
            st.session_state.stocks = filter_growth_dividends_stocks(st.session_state.stocks)

            st.session_state[f"{selected_portfolio}_investor_birth_date"] = DEFAULT_INVESTOR_BIRTH_DATE
            age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)

            try:
                targets_data = calculate_portfolio_targets(age)
                unified_targets = targets_data["targets"]
            except Exception as e:
                st.error(f"Error calculating Growth Targets: {e}")
                unified_targets = {}
            
            for i, stock in enumerate(st.session_state.stocks):
                ticker = stock['name']
                if ticker in unified_targets:
                    stock['target_allocation'] = unified_targets[ticker]
                    stock['tolerance'] = get_tolerance_for_ticker(ticker, unified_targets)
                    st.session_state[f"{selected_portfolio}_{i}_tolerance"] = stock['tolerance']
                    st.session_state[f"{selected_portfolio}_{i}_target"] = stock['target_allocation']
                else:
                    stock['target_allocation'] = 0.0
                    stock['tolerance'] = get_tolerance_for_ticker(ticker, unified_targets)

    # Sidebar utilities (Configuration and monthly investment)
    with st.sidebar:
        if selected_portfolio and selected_portfolio != GLOBAL_OVERVIEW_LABEL:
            if p_type == "Kids":
                birth_date_key = f"{selected_portfolio}_birth_date"
                current_birth_date = st.session_state.get(birth_date_key, '')

                try:
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
                    on_change=clear_recommendations,
                )

                if str(birth_date_input) != current_birth_date:
                    st.session_state[birth_date_key] = str(birth_date_input)
                    st.session_state.has_unsaved_changes = True

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
                                st.session_state.stocks.append({
                                    "name": ticker,
                                    "current_value": 0.0,
                                    "target_allocation": target,
                                    "tolerance": 2.0,
                                    "expense_ratio": 0.0,
                                    "full_name": ticker,
                                    "sector": "", "industry": "", "country": "",
                                    "currency": "EUR", "quantity": 0.0,
                                    "average_price": 0.0, "dividend_yield": 0.0,
                                })
                        st.toast("👶 Age-based targets updated!", icon="✅")
                        st.rerun()

            if p_type == PORTFOLIO_TYPE_GROWTH:
                st.session_state[f"{selected_portfolio}_investor_birth_date"] = (
                    DEFAULT_INVESTOR_BIRTH_DATE
                )
                growth_age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)
                if cash_split(growth_age) > 0:
                    safe_liquidity_key = f"{selected_portfolio}_safe_liquidity"
                    current_safe_liquidity = get_portfolio_safe_liquidity(selected_portfolio)
                    safe_liquidity_input = st.number_input(
                        "Safe Liquidity Balance (€)",
                        min_value=0.0,
                        value=current_safe_liquidity,
                        step=1.0,
                        format="%.2f",
                        key=f"{safe_liquidity_key}_input",
                        on_change=clear_recommendations,
                    )
                    if abs(float(safe_liquidity_input) - current_safe_liquidity) > 0.01:
                        set_portfolio_safe_liquidity(selected_portfolio, safe_liquidity_input)
                        st.session_state.has_unsaved_changes = True

            if p_type in ["Kids", PORTFOLIO_TYPE_GROWTH]:
                now = datetime.now()

                if now.day >= 28:
                    if now.month == 12:
                        investment_month, investment_year = 1, now.year + 1
                    else:
                        investment_month, investment_year = now.month + 1, now.year
                else:
                    investment_month, investment_year = now.month, now.year
                
                if p_type == "Kids":
                    base_investment = 100.0 if investment_month in [6, 12] else 50.0
                else:
                    monthly_invest_key = f"{selected_portfolio}_monthly_invest"
                    defined_monthly = get_portfolio_monthly_contribution_setting(
                        selected_portfolio
                    )
                    monthly_input = st.number_input(
                        "Monthly contribution (€)",
                        min_value=0.0,
                        value=defined_monthly,
                        step=50.0,
                        format="%.2f",
                        key=f"{monthly_invest_key}_sidebar",
                        on_change=clear_recommendations,
                    )
                    if abs(float(monthly_input) - defined_monthly) > 0.01:
                        st.session_state[monthly_invest_key] = float(monthly_input)
                        st.session_state.has_unsaved_changes = True

                    base_investment = growth_monthly_base_contribution(
                        selected_portfolio, investment_month
                    )

                monthly_investment = contribution_with_uninvested(
                    selected_portfolio, base_investment
                )

            elif p_type not in ("Kids", PORTFOLIO_TYPE_GROWTH):
                monthly_investment = 0.0
                use_market_indicators = False

        elif not selected_portfolio:
            monthly_investment = 1000.0  # Default fallback for later logic
        else:
            monthly_investment = 0.0



    # Main content
    if selected_portfolio == GLOBAL_OVERVIEW_LABEL:
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
        if p_type == PORTFOLIO_TYPE_GROWTH:
            live_stocks = filter_growth_dividends_stocks(live_stocks)
        
        # Custom sort order: EGLN placed immediately after VFEA.DE
        custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"]
        live_stocks.sort(key=lambda x: custom_order_list.index(x.get('name', '')) if x.get('name', '') in custom_order_list else 99)

        # --- Top Row: KPI Cards ---
        total_current = sum(s['current_value'] for s in live_stocks)
        total_target = sum(s['target_allocation'] for s in live_stocks)
        num_stocks = len(live_stocks)
        
        # Dashboard Header
        formatted_title = (
            format_portfolio_nav_label(selected_portfolio)
            if selected_portfolio
            else "📊 Portfolio"
        )
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
            purchases_kpi = list(
                st.session_state.get(stock_purchases_session_key(selected_portfolio), [])
            )
            overrides_kpi = dict(
                st.session_state.get(stock_market_overrides_key(selected_portfolio), {})
            )
            total_invested = sum(
                s["invested_value"]
                for s in aggregate_stock_purchases(
                    purchases_kpi, {}, overrides_kpi
                )
            )
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

            profit_value_html = (
                f'<div class="kpi-value-stack">'
                f'<div class="kpi-value {profit_class}">€{profit_prefix}{profit:,.2f}</div>'
                f'<div class="kpi-subvalue {profit_class}">'
                f"{profit_prefix}{profit_pct:.2f}%</div></div>"
            )

            kpi_row1 = st.columns(4, gap="small", vertical_alignment="top")
            with kpi_row1[0]:
                render_kpi_card("Total Market Value", f"€{total_current:,.2f}")
            with kpi_row1[1]:
                render_kpi_card("Total Invested", f"€{total_invested:,.2f}")
            with kpi_row1[2]:
                render_kpi_card("Profit", profit_value_html, value_html=True)
            with kpi_row1[3]:
                render_kpi_card("Volumes Count", f"{total_volume:,.0f}")

            kpi_row2 = st.columns(4, gap="small", vertical_alignment="top")
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
            if p_type in ("Kids", PORTFOLIO_TYPE_GROWTH):
                total_invested = get_total_invested(username, selected_portfolio, conn)
                with kpi_cols[3]: render_kpi_card("Total Invested", f"€{total_invested:,.2f}")
            else:
                with kpi_cols[3]: render_kpi_card("Monthly Budget", f"€{monthly_investment:,.2f}")
        
        if p_type != "Stocks" and abs(total_target - 100.0) > 0.01:
            st.warning("⚠️ Your target allocations do not sum to 100%. Please adjust them in Portfolio Management.")

        # --- Tab Routing Logic ---
        
        tab_list = []
        if p_type == "Stocks":
            tab_list = ["📈 Portfolio Details", "💰 Dividend Tracker", "🪙 Uninvested Cash"]
        elif p_type == PORTFOLIO_TYPE_GROWTH:
            tab_list = ["📊 Manage Portfolio", "🪙 Uninvested Cash"]
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
                if p_type == PORTFOLIO_TYPE_GROWTH:
                    _liq_age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)
                    if cash_split(_liq_age) > 0:
                        safe_liquidity = get_portfolio_safe_liquidity(selected_portfolio)
                        if safe_liquidity > 0:
                            st.info(
                                f"💡 **Safe liquidity balance:** €{safe_liquidity:,.2f} "
                                f"(stored separately from Uninvested Cash).",
                                icon="🛡️",
                            )

                col_main, col_side = st.columns([2, 1])
        
                with col_main:
                    with st.container(border=True):
                        st.subheader("📝 Portfolio Management")
                        
                        # Prepare data for Editor
                        editor_stocks = st.session_state.stocks
                        if p_type == PORTFOLIO_TYPE_GROWTH:
                            editor_stocks = filter_growth_dividends_stocks(editor_stocks)
                        current_stocks_df = pd.DataFrame(editor_stocks)
                        if not current_stocks_df.empty:
                            # Slice to only include core rebalancing columns for this tab
                            # Keep 'name' as a column to style the ticker too
                            core_cols = ["name", "current_value", "target_allocation", "tolerance", "expense_ratio"]
                            
                            available_core = [c for c in core_cols if c in current_stocks_df.columns]
                            current_stocks_df = current_stocks_df[available_core]



                            # Custom order logic
                            custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"]
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
                                disabled=(p_type in ["Kids", PORTFOLIO_TYPE_GROWTH])
                            ),
                            "current_price": st.column_config.NumberColumn("Price (€)", min_value=0.0, step=0.01, format="%.2f"),
                            "tolerance": st.column_config.NumberColumn(
                                "Tolerance %", min_value=0.0, max_value=20.0, step=0.1, format="%.1f%%",
                                disabled=(p_type == PORTFOLIO_TYPE_GROWTH)
                            ),
                            "expense_ratio": st.column_config.NumberColumn(
                                "TER %",
                                min_value=0.0,
                                max_value=5.0,
                                step=0.01,
                                format="%.2f%%",
                                disabled=True,
                            )
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
                            except (ValueError, TypeError):
                                portfolio_uninvested_cash = 0.0
                            portfolio_safe_liquidity = get_portfolio_safe_liquidity(selected_portfolio)
                            portfolio_type = p_type
                            portfolio_investor_birth = DEFAULT_INVESTOR_BIRTH_DATE
                            portfolio_uninvested_reinvested = (
                                get_portfolio_uninvested_reinvested(selected_portfolio)
                                if portfolio_type == PORTFOLIO_TYPE_GROWTH
                                else 0.0
                            )

                            mask = (data['username'] == username) & (data['portfolio_name'] == selected_portfolio)
                            
                            # Check for Config Changes
                            if not user_portfolio_df.empty:
                                fr = user_portfolio_df.iloc[0]
                                try:
                                    fr_cash = float(fr.get('portfolio_uninvested_cash', 0.0))
                                except (ValueError, TypeError):
                                    fr_cash = 0.0
                                try:
                                    fr_safe = float(fr.get('portfolio_safe_liquidity', 0.0))
                                except (ValueError, TypeError):
                                    fr_safe = 0.0
                                if (abs(portfolio_invest - fr.get('portfolio_monthly_invest', 1000.0)) > 0.1 or
                                    portfolio_use_ind != fr.get('portfolio_use_indicators', False) or
                                    portfolio_birth_date != fr.get('portfolio_birth_date', '') or
                                    abs(portfolio_uninvested_cash - fr_cash) > 0.01 or
                                    abs(portfolio_safe_liquidity - fr_safe) > 0.01 or
                                    portfolio_investor_birth != fr.get('investor_birth_date', DEFAULT_INVESTOR_BIRTH_DATE) or
                                    abs(portfolio_buffett - fr.get('portfolio_buffett_index', 195.0)) > 0.1):
                                    any_content_changes = True
                                    data.loc[mask, 'portfolio_monthly_invest'] = portfolio_invest
                                    data.loc[mask, 'portfolio_use_indicators'] = portfolio_use_ind
                                    data.loc[mask, 'portfolio_buffett_index'] = portfolio_buffett
                                    data.loc[mask, 'portfolio_birth_date'] = portfolio_birth_date
                                    data.loc[mask, 'portfolio_uninvested_cash'] = portfolio_uninvested_cash
                                    data.loc[mask, 'portfolio_safe_liquidity'] = portfolio_safe_liquidity
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
                                        "portfolio_safe_liquidity": portfolio_safe_liquidity,
                                        "portfolio_uninvested_reinvested": portfolio_uninvested_reinvested,
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
                                    "portfolio_birth_date": portfolio_birth_date,
                                    "portfolio_uninvested_cash": portfolio_uninvested_cash,
                                    "portfolio_safe_liquidity": portfolio_safe_liquidity,
                                    "portfolio_uninvested_reinvested": portfolio_uninvested_reinvested,
                                    "investor_birth_date": portfolio_investor_birth,
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
                            if p_type == PORTFOLIO_TYPE_GROWTH:
                                import copy
                                live_stocks = filter_growth_dividends_stocks(copy.deepcopy(st.session_state.stocks))
                                current_monthly_base = float(monthly_investment)
                                uninvested_included = get_portfolio_uninvested_cash(
                                    selected_portfolio
                                )
                                
                                current_values = {s['name']: s['current_value'] for s in live_stocks}
                                
                                age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)
                                
                                try:
                                    safe_liquidity_before = get_portfolio_safe_liquidity(
                                        selected_portfolio
                                    )
                                    buys_data = allocate_contribution(
                                        contribution=current_monthly_base,
                                        age=age,
                                        current_values=current_values,
                                        min_order_size=5.0,
                                    )

                                    portfolio_targets = buys_data["portfolio_targets"]
                                    cash_part = buys_data["cash_part"]
                                    cash_split_pct = buys_data["cash_split"] * 100.0
                                    safe_liquidity_after = safe_liquidity_before + cash_part

                                    withdrawal_data = None
                                    if age >= RETIREMENT_AGE:
                                        withdrawal_data = retirement_withdrawal_plan(
                                            current_values,
                                            age,
                                            cash_buffer=safe_liquidity_before,
                                        )
                                    
                                except Exception as e:
                                    st.error(f"Error calculating Growth buys: {e}")
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

                                if cash_part > 0 or safe_liquidity_before > 0:
                                    safe_pct = (
                                        safe_liquidity_before / portfolio_value_after * 100
                                        if portfolio_value_after > 0 else 0.0
                                    )
                                    new_safe_pct = (
                                        safe_liquidity_after / portfolio_value_after * 100
                                        if portfolio_value_after > 0 else 0.0
                                    )
                                    allocations.append({
                                        "Stock": SAFE_LIQUIDITY_LABEL,
                                        "Current Value": safe_liquidity_before,
                                        "Current %": safe_pct,
                                        "TER %": 0.0,
                                        "Target %": cash_split_pct,
                                        "Target Value": portfolio_value_after * (cash_split_pct / 100.0),
                                        "Investment": cash_part,
                                        "New Value": safe_liquidity_after,
                                        "New %": new_safe_pct,
                                    })
                                
                                invest_map = buys_map
                                total_current_live = portfolio_value_before
                                remaining_investment = leftover_cash
                                
                                if 'vault_alloc_by_portfolio' not in st.session_state:
                                    st.session_state.vault_alloc_by_portfolio = {}
                                st.session_state.vault_alloc_by_portfolio[selected_portfolio] = {
                                    "type": p_type,
                                    "EGLN.UK": buys_map.get("EGLN.UK", 0.0),
                                }
                                
                                import pandas as pd
                                alloc_df = pd.DataFrame(allocations)
                                if not alloc_df.empty:
                                    custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"]
                                    alloc_df['order_idx'] = alloc_df['Stock'].apply(lambda x: custom_order_list.index(x) if x in custom_order_list else 99)
                                    alloc_df = alloc_df.sort_values(by='order_idx').drop(columns=['order_idx'])
                                    
                                st.session_state.last_calculation = {
                                    "df": alloc_df,
                                    "monthly_investment": current_monthly_base,
                                    "base_contribution": round(
                                        current_monthly_base - uninvested_included, 2
                                    ),
                                    "uninvested_included": uninvested_included,
                                    "remaining": remaining_investment,
                                    "cash_reserve": cash_part,
                                    "cash_split_pct": cash_split_pct,
                                    "safe_liquidity_before": safe_liquidity_before,
                                    "safe_liquidity_after": safe_liquidity_after,
                                    "withdrawal": withdrawal_data,
                                    "investor_age": age,
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
                                    custom_order_list = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"]
                                    alloc_df['order_idx'] = alloc_df['Stock'].apply(lambda x: custom_order_list.index(x) if x in custom_order_list else 99)
                                    alloc_df = alloc_df.sort_values(by='order_idx').drop(columns=['order_idx'])

                                st.session_state.last_calculation = {"df": alloc_df, "monthly_investment": current_monthly_base, "remaining": remaining_investment}
                                st.session_state.show_recommendations = True
                                
                                # Persist vault allocations per portfolio so the Hedges tab can aggregate them
                                if 'vault_alloc_by_portfolio' not in st.session_state:
                                    st.session_state.vault_alloc_by_portfolio = {}
                                st.session_state.vault_alloc_by_portfolio[selected_portfolio] = {
                                    "type": p_type,
                                    "EGLN.UK": final_investments.get("EGLN.UK", 0.0),
                                }
                        
                        if st.session_state.show_recommendations:
                            calc = st.session_state.last_calculation
                            if calc['remaining'] > 0.01:
                                st.warning(f"Note: €{calc['remaining']:.2f} could not be allocated.")
                            st.success("Allocation Calculated!")
        
                # --- Bottom Row: Results & Visualization ---
                if st.session_state.show_recommendations:
                    with st.container(border=True):
                        st.subheader("📋 Investment Recommendations")
                        df = st.session_state.last_calculation['df']
                        if p_type == PORTFOLIO_TYPE_GROWTH and not df.empty:
                            df = df[~df['Stock'].str.upper().isin(EXCLUDED_GD_TICKERS)].copy()
                        
                        if p_type == PORTFOLIO_TYPE_GROWTH:
                            calc = st.session_state.last_calculation
                            etf_mask = df['Stock'] != SAFE_LIQUIDITY_LABEL
                            total_etf_investment = float(
                                df.loc[etf_mask, 'Investment'].sum()
                            )
                            safe_liquidity = float(calc.get('cash_reserve', 0.0))
                            safe_balance_after = float(
                                calc.get(
                                    'safe_liquidity_after',
                                    get_portfolio_safe_liquidity(selected_portfolio) + safe_liquidity,
                                )
                            )

                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(
                                    f"""
                                    <div style="background-color: #2D2D3A; padding: 20px; border-radius: 12px; border-left: 6px solid #24A16F; margin-bottom: 20px;">
                                        <span style="font-size: 1.1rem; font-weight: 600; color: #E5E7EB;">Total ETF Investment</span><br>
                                        <span style="font-size: 2.2rem; font-weight: 700; color: #24A16F;">€{total_etf_investment:,.2f}</span>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            with col2:
                                st.markdown(
                                    f"""
                                    <div style="background-color: #2D2D3A; padding: 20px; border-radius: 12px; border-left: 6px solid #6366F1; margin-bottom: 20px;">
                                        <span style="font-size: 1.1rem; font-weight: 600; color: #E5E7EB;">Safe Liquidity</span><br>
                                        <span style="font-size: 2.2rem; font-weight: 700; color: #6366F1;">€{safe_balance_after:,.2f}</span>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                            investor_age = calc.get("investor_age")
                            if investor_age is None:
                                investor_age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)

                            withdrawal = calc.get("withdrawal")
                            if investor_age >= RETIREMENT_AGE and withdrawal:
                                w_amount = withdrawal["withdrawal_amount"]
                                from_buffer = withdrawal.get("from_cash_buffer", 0.0)
                                shortfall = withdrawal.get("shortfall", 0.0)
                                etf_sells = withdrawal.get("etf_sells", {})
                                used_fallback = withdrawal.get("used_proportional_fallback", False)

                                col3, col4 = st.columns(2)
                                with col3:
                                    st.markdown(
                                        f"""
                                        <div style="background-color: #2D2D3A; padding: 20px; border-radius: 12px; border-left: 6px solid #3B82F6; margin-bottom: 20px;">
                                            <span style="font-size: 1.1rem; font-weight: 600; color: #E5E7EB;">Annual Spending</span><br>
                                            <span style="font-size: 2.2rem; font-weight: 700; color: #3B82F6;">€{w_amount:,.2f}</span>
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )
                                with col4:
                                    withdrawal_lines = [
                                        f"Safe liquidity: €{from_buffer:,.2f}",
                                    ]
                                    if shortfall > 0 and etf_sells:
                                        sell_parts = [
                                            f"{ticker}: €{sell_amt:,.2f}"
                                            for ticker, sell_amt in sorted(
                                                etf_sells.items(), key=lambda x: x[1], reverse=True
                                            )
                                            if sell_amt > 0
                                        ]
                                        etf_line = f"ETF sales: €{shortfall:,.2f}"
                                        if sell_parts:
                                            etf_line += f" ({'; '.join(sell_parts)})"
                                        withdrawal_lines.append(etf_line)
                                        if used_fallback:
                                            withdrawal_lines.append(
                                                "Part of ETF sales uses proportional split "
                                                "(no asset above target)."
                                            )
                                    elif shortfall <= 0:
                                        withdrawal_lines.append(
                                            "ETF sales: €0.00 (covered by safe liquidity)"
                                        )
                                    else:
                                        withdrawal_lines.append(
                                            f"ETF sales: €{shortfall:,.2f}"
                                        )
                                    withdrawal_body = "<br>".join(
                                        f'<span style="font-size: 0.95rem; color: #D1D5DB;">{line}</span>'
                                        for line in withdrawal_lines
                                    )
                                    st.markdown(
                                        f"""
                                        <div style="background-color: #2D2D3A; padding: 20px; border-radius: 12px; border-left: 6px solid #8B5CF6; margin-bottom: 20px;">
                                            <span style="font-size: 1.1rem; font-weight: 600; color: #E5E7EB;">Withdrawal Sources</span><br><br>
                                            {withdrawal_body}
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )
                        
                        # Create a display-only version by dropping columns requested by user
                        display_df = df.drop(columns=["TER %", "Target Value"])
                        
                        def style_rows(row):
                            base = ''
                            invest_amt = float(pd.to_numeric(row.get('Investment', 0), errors='coerce') or 0)
                            if invest_amt > 0.005:
                                if row['Stock'] == SAFE_LIQUIDITY_LABEL:
                                    invest_style = (
                                        'background-color: #6366F1; color: white; font-weight: 700; '
                                        'border-bottom: 1px solid #4338CA;'
                                    )
                                else:
                                    invest_style = (
                                        'background-color: #24A16F; color: white; font-weight: 700; '
                                        'border-bottom: 1px solid #065F46;'
                                    )
                            else:
                                invest_style = base

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
                                    load_investment_log(conn, force_reload=True)

                                    # --- APPLY NEW VALUES TO PORTFOLIO ---
                                    master_data = st.session_state.master_data.copy()
                                    # Update master_data with New Value for each stock in the current portfolio
                                    for _, row in df.iterrows():
                                        stock_ticker = row['Stock']
                                        if stock_ticker == SAFE_LIQUIDITY_LABEL:
                                            continue
                                        new_val = row['New Value']
                                        
                                        mask = (master_data['username'] == username) & \
                                               (master_data['portfolio_name'] == selected_portfolio) & \
                                               (master_data['stock_name'] == stock_ticker)
                                        
                                        if mask.any():
                                            master_data.loc[mask, 'current_value'] = new_val

                                    if p_type == PORTFOLIO_TYPE_GROWTH:
                                        safe_row = df[df['Stock'] == SAFE_LIQUIDITY_LABEL]
                                        if not safe_row.empty:
                                            new_safe = float(safe_row.iloc[0]['New Value'])
                                        else:
                                            new_safe = float(
                                                st.session_state.last_calculation.get(
                                                    'safe_liquidity_after',
                                                    get_portfolio_safe_liquidity(selected_portfolio),
                                                )
                                            )
                                        set_portfolio_safe_liquidity(selected_portfolio, new_safe)
                                        portfolio_mask = (
                                            (master_data['username'] == username)
                                            & (master_data['portfolio_name'] == selected_portfolio)
                                        )
                                        if portfolio_mask.any():
                                            master_data.loc[portfolio_mask, 'portfolio_safe_liquidity'] = new_safe

                                        reinvested_add = float(
                                            st.session_state.last_calculation.get(
                                                "uninvested_included", 0.0
                                            )
                                        )
                                        if reinvested_add > 0:
                                            new_reinvested = (
                                                get_portfolio_uninvested_reinvested(
                                                    selected_portfolio
                                                )
                                                + reinvested_add
                                            )
                                            set_portfolio_uninvested_reinvested(
                                                selected_portfolio, new_reinvested
                                            )
                                            new_uninv = max(
                                                0.0,
                                                get_portfolio_uninvested_cash(
                                                    selected_portfolio
                                                )
                                                - reinvested_add,
                                            )
                                            st.session_state[
                                                f"{selected_portfolio}_uninvested_cash"
                                            ] = round(new_uninv, 2)
                                            if portfolio_mask.any():
                                                master_data.loc[
                                                    portfolio_mask,
                                                    "portfolio_uninvested_reinvested",
                                                ] = new_reinvested
                                                master_data.loc[
                                                    portfolio_mask,
                                                    "portfolio_uninvested_cash",
                                                ] = new_uninv
                                    
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
                        df_plot = df[~df['Stock'].isin(["EGLN.UK"])].sort_values('Stock')
                        
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

                        if not df.empty and "Current Value" in df.columns:
                            chart_total_value = float(
                                pd.to_numeric(df["Current Value"], errors="coerce")
                                .fillna(0)
                                .sum()
                            )
                        else:
                            chart_total_value = sum(
                                float(s.get("current_value", 0) or 0) for s in live_stocks
                            )
                            if p_type == PORTFOLIO_TYPE_GROWTH:
                                chart_total_value += get_portfolio_safe_liquidity(
                                    selected_portfolio
                                )
                        if p_type == PORTFOLIO_TYPE_GROWTH:
                            chart_total_invested = get_total_invested(
                                username, selected_portfolio, conn
                            )
                        else:
                            inv_log = load_investment_log(conn)
                            if inv_log.empty or "Investment" not in inv_log.columns:
                                chart_total_invested = 0.0
                            else:
                                inv_mask = (
                                    (inv_log["username"].astype(str) == str(username))
                                    & (
                                        inv_log["portfolio_name"].astype(str)
                                        == str(selected_portfolio)
                                    )
                                )
                                chart_total_invested = round(
                                    float(
                                        pd.to_numeric(
                                            inv_log.loc[inv_mask, "Investment"],
                                            errors="coerce",
                                        )
                                        .fillna(0)
                                        .sum()
                                    ),
                                    2,
                                )
                        ts_df = build_monthly_value_invested_series(
                            username,
                            selected_portfolio,
                            conn,
                            current_total_value=chart_total_value,
                            current_total_invested=chart_total_invested,
                        )
                        if not ts_df.empty and ts_df["total_value"].notna().any():
                            fig_ts = go.Figure()
                            fig_ts.add_trace(
                                go.Scatter(
                                    x=ts_df["month_label"],
                                    y=ts_df["total_value"],
                                    mode="lines+markers",
                                    name="Total Value",
                                    line=dict(color="#3B82F6", width=2),
                                    marker=dict(size=7),
                                    hovertemplate=(
                                        "Total Value: %{y:.2f}<extra></extra>"
                                    ),
                                )
                            )
                            if "total_invested" in ts_df.columns and ts_df[
                                "total_invested"
                            ].notna().any():
                                add_invested_line_with_gradient_fill(
                                    fig_ts,
                                    ts_df["month_label"],
                                    ts_df["total_invested"],
                                )
                            fig_ts.update_layout(
                                title=dict(
                                    text="<b>Total Value vs Total Invested</b>",
                                    x=0.5,
                                    xanchor="center",
                                    y=0.98,
                                    yanchor="top",
                                    font=dict(size=18, color="white"),
                                ),
                                xaxis_title="Month",
                                paper_bgcolor="rgba(0,0,0,0)",
                                plot_bgcolor="rgba(0,0,0,0)",
                                font=dict(color="#E5E7EB"),
                                legend=dict(
                                    orientation="h",
                                    yanchor="bottom",
                                    y=1.02,
                                    xanchor="center",
                                    x=0.5,
                                ),
                                margin=dict(t=80, b=50, l=50, r=40),
                                height=400,
                                xaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
                                yaxis=dict(
                                    gridcolor="rgba(255,255,255,0.08)",
                                    tickformat=".2f",
                                    exponentformat="none",
                                    separatethousands=False,
                                ),
                            )
                            fig_ts.update_traces(hoverlabel=dict(namelength=-1))
                            fig_ts.update_yaxes(hoverformat=".2f")
                            st.plotly_chart(fig_ts, use_container_width=True)
                        else:
                            st.caption(
                                "Log at least one allocation to see value and invested over time."
                            )

        if "📈 Portfolio Details" in tab_map:
            with tab_map["📈 Portfolio Details"]:
                st.session_state.footer_msg = "<b>Data Insight:</b> Visualize your diversification and asset health."
                uninvested_cash = float(st.session_state.get(f"{selected_portfolio}_uninvested_cash", 0.0))
                if uninvested_cash > 0:
                    st.info(f"💡 You have **€{uninvested_cash:,.2f}** of uninvested cash. You can manage it in the 'Uninvested Cash' tab.", icon="🪙")
                if p_type == PORTFOLIO_TYPE_GROWTH:
                    _liq_age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)
                    if cash_split(_liq_age) > 0:
                        safe_liquidity = get_portfolio_safe_liquidity(selected_portfolio)
                        if safe_liquidity > 0:
                            st.info(
                                f"💡 **Safe liquidity balance:** €{safe_liquidity:,.2f} "
                                f"(stored separately from Uninvested Cash).",
                                icon="🛡️",
                            )

                with st.container(border=True):
                    st.subheader("📈 Detailed Portfolio Information")

                    if p_type == "Stocks":
                        purchases = list(
                            st.session_state.get(
                                stock_purchases_session_key(selected_portfolio), []
                            )
                        )
                        market_overrides = dict(
                            st.session_state.get(
                                stock_market_overrides_key(selected_portfolio), {}
                            )
                        )
                        dividend_map: Dict[str, float] = {}
                        df_divs = st.session_state.dividends
                        if not df_divs.empty:
                            df_divs = df_divs.copy()
                            df_divs["amount"] = pd.to_numeric(
                                df_divs["amount"], errors="coerce"
                            ).fillna(0.0)
                            div_mask = (df_divs["username"] == username) & (
                                df_divs["portfolio_name"] == selected_portfolio
                            )
                            dividend_map = (
                                df_divs.loc[div_mask]
                                .groupby("ticker")["amount"]
                                .sum()
                                .to_dict()
                            )

                        summaries = aggregate_stock_purchases(
                            purchases, dividend_map, market_overrides
                        )
                        total_mv = sum(s["market_value"] for s in summaries)

                        if st.button("➕ Add purchase", key="stocks_add_purchase_btn"):
                            stocks_add_purchase_dialog(selected_portfolio)

                        if not summaries:
                            st.info(
                                "No purchases yet. Use **Add purchase** to register buys."
                            )
                        else:
                            summary_rows = []
                            for summary in summaries:
                                summary_rows.append(
                                    {
                                        "Ticker": summary["ticker"],
                                        "Current %": (
                                            summary["market_value"] / total_mv * 100.0
                                            if total_mv > 0
                                            else 0.0
                                        ),
                                        "Market Value": summary["market_value"],
                                        "Invested Value": summary["invested_value"],
                                        "Quantity": int(round(summary["quantity"])),
                                        "Avg. Price": summary["avg_price"],
                                        "Div. Yield (%)": summary["div_yield"],
                                        "YoC (%)": summary["yoc"],
                                        "Received YoC (%)": summary["received_yoc"],
                                        "Sell Price": summary["above_avg_15"],
                                        "Buy Price": summary["below_lowest_10"],
                                    }
                                )
                            summary_display_df = pd.DataFrame(summary_rows).set_index(
                                "Ticker"
                            )
                            stocks_column_config = {
                                "_index": st.column_config.TextColumn(
                                    "Ticker", disabled=True
                                ),
                                "Current %": st.column_config.NumberColumn(
                                    "Current %", format="%.2f%%", disabled=True
                                ),
                                "Market Value": st.column_config.NumberColumn(
                                    "Market Value (€)",
                                    min_value=0.0,
                                    step=0.01,
                                    format="%.2f",
                                ),
                                "Invested Value": st.column_config.NumberColumn(
                                    "Invested Value (€)", format="%.2f", disabled=True
                                ),
                                "Quantity": st.column_config.NumberColumn(
                                    "Quantity", format="%.0f", disabled=True
                                ),
                                "Avg. Price": st.column_config.NumberColumn(
                                    format="%.4f", disabled=True
                                ),
                                "Div. Yield (%)": st.column_config.NumberColumn(
                                    format="%.2f%%", disabled=True
                                ),
                                "YoC (%)": st.column_config.NumberColumn(
                                    format="%.2f%%", disabled=True
                                ),
                                "Received YoC (%)": st.column_config.NumberColumn(
                                    format="%.2f%%", disabled=True
                                ),
                                "Sell Price": st.column_config.NumberColumn(
                                    "Sell Price", format="%.4f", disabled=True
                                ),
                                "Buy Price": st.column_config.NumberColumn(
                                    "Buy Price", format="%.4f", disabled=True
                                ),
                            }
                            edited_summary_df = st.data_editor(
                                style_stocks_summary_for_editor(summary_display_df),
                                column_config=stocks_column_config,
                                disabled=[
                                    "Current %",
                                    "Invested Value",
                                    "Quantity",
                                    "Avg. Price",
                                    "Div. Yield (%)",
                                    "YoC (%)",
                                    "Received YoC (%)",
                                    "Sell Price",
                                    "Buy Price",
                                ],
                                use_container_width=True,
                                num_rows="fixed",
                                hide_index=False,
                                key=f"stocks_summary_editor_{st.session_state.editor_key}",
                                on_change=clear_recommendations,
                            )
                            mv_before = summary_display_df["Market Value"].astype(float)
                            mv_after = edited_summary_df["Market Value"].astype(float)
                            if not mv_after.sort_index().equals(mv_before.sort_index()):
                                updated_overrides = dict(market_overrides)
                                for ticker, row in edited_summary_df.iterrows():
                                    updated_overrides[str(ticker).upper()] = float(
                                        row["Market Value"]
                                    )
                                st.session_state[
                                    stock_market_overrides_key(selected_portfolio)
                                ] = updated_overrides
                                sync_stocks_from_purchases(
                                    selected_portfolio, purchases, updated_overrides
                                )
                                st.session_state.has_unsaved_changes = True
                                st.rerun()

                        with st.expander("Manage purchases", expanded=False):
                            if not purchases:
                                st.caption("No purchases recorded.")
                            else:
                                render_manage_stock_purchases_units(
                                    selected_portfolio, purchases
                                )

                    if p_type != "Stocks":
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

                        details_stocks = st.session_state.stocks
                        if p_type == PORTFOLIO_TYPE_GROWTH:
                            details_stocks = filter_growth_dividends_stocks(details_stocks)
                        details_df = pd.DataFrame(details_stocks)
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
                        portfolio_safe_liquidity = (
                            get_portfolio_safe_liquidity(selected_portfolio)
                            if portfolio_type == PORTFOLIO_TYPE_GROWTH
                            else 0.0
                        )
                        portfolio_investor_birth = DEFAULT_INVESTOR_BIRTH_DATE
                        portfolio_uninvested_reinvested = (
                            get_portfolio_uninvested_reinvested(selected_portfolio)
                            if portfolio_type == PORTFOLIO_TYPE_GROWTH
                            else 0.0
                        )

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
                                    "portfolio_birth_date": portfolio_birth_date,
                                    "portfolio_uninvested_cash": portfolio_uninvested_cash,
                                    "portfolio_safe_liquidity": portfolio_safe_liquidity,
                                    "portfolio_uninvested_reinvested": portfolio_uninvested_reinvested,
                                    "investor_birth_date": portfolio_investor_birth,
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
                                "portfolio_safe_liquidity": portfolio_safe_liquidity,
                                "portfolio_uninvested_reinvested": portfolio_uninvested_reinvested,
                                "investor_birth_date": portfolio_investor_birth,
                                "portfolio_type": portfolio_type,
                                "stock_full_name": '', "sector": '', "industry": '', "country": '', "currency": '', "quantity": 0.0, "average_price": 0.0, "dividend_yield": 0.0
                            })
                        
                        updated_data = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
                        st.session_state.master_data = updated_data
                        conn.update(worksheet="Portfolios", data=updated_data)

                        if p_type == "Stocks":
                            purchases_to_save = st.session_state.get(
                                stock_purchases_session_key(selected_portfolio), []
                            )
                            persist_stock_purchases(
                                conn, username, selected_portfolio, purchases_to_save
                            )
                        
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
                                    "date": f"{div_date} 00:00:00",
                                    "ticker": div_ticker,
                                    "amount": div_amount,
                                    "portfolio_name": selected_portfolio,
                                    "username": username
                                }
                                # Fetch freshest data from Google Sheets first to avoid overwriting edits from other sessions
                                fresh_divs = conn.read(worksheet="Dividends", ttl=0)
                                if fresh_divs is None or fresh_divs.empty:
                                    fresh_divs = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])
                                
                                new_row_df = pd.DataFrame([new_div])
                                updated_divs = pd.concat([fresh_divs, new_row_df], ignore_index=True)
                                
                                st.session_state.dividends = updated_divs
                                conn.update(worksheet="Dividends", data=updated_divs)
                                conn.reset() # Invalidate GSheetsConnection cache to ensure live data load
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
                                    
                                    my_divs['MonthNum'] = my_divs['date'].dt.month
                                    
                                    # Aggregated stats (grouped by Year and MonthNum to be 100% locale-independent)
                                    actual_stats = my_divs.groupby(['Year', 'MonthNum'])['amount'].sum().reset_index()
                                    
                                    # Create a template for all 12 months for BOTH years to ensure a full X-axis
                                    template_rows = []
                                    for yr in [str(current_year), str(current_year-1)]:
                                        for m_num in range(1, 13):
                                            template_rows.append({'Year': yr, 'MonthNum': m_num})
                                    
                                    template_df = pd.DataFrame(template_rows)
                                    
                                    # Merge actual data into template
                                    monthly_stats = pd.merge(template_df, actual_stats, on=['Year', 'MonthNum'], how='left').fillna(0.0)
                                    
                                    # Map MonthNum to English 3-letter month abbreviations for plotting
                                    month_map = {
                                        1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                                        7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
                                    }
                                    monthly_stats['Month'] = monthly_stats['MonthNum'].map(month_map)
                                    
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
                                                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", required=True),
                                                "ticker": st.column_config.SelectboxColumn("Ticker", options=portfolio_tickers, required=True),
                                                "amount": st.column_config.NumberColumn("Amount (€)", min_value=0.0, format="€%.2f", required=True),
                                            },
                                            use_container_width=True,
                                            num_rows="dynamic",
                                            key=f"div_history_editor_{st.session_state.get('editor_key', 0)}"
                                        )
                                        
                                        if st.button("💾 Save History Changes", width="stretch", key="save_div_hist"):
                                            # Fetch freshest data from Google Sheets first to avoid overwriting edits from other sessions
                                            fresh_divs = conn.read(worksheet="Dividends", ttl=0)
                                            if fresh_divs is None or fresh_divs.empty:
                                                fresh_divs = pd.DataFrame(columns=['date', 'ticker', 'amount', 'portfolio_name', 'username'])
                                            
                                            # Drop old records for ONLY this specific user and portfolio to keep other edits intact
                                            other_dividends = fresh_divs[~((fresh_divs['username'] == username) & (fresh_divs['portfolio_name'] == selected_portfolio))]
                                            
                                            new_records = []
                                            for _, row in edited_history.iterrows():
                                                row_date = row.get('date')
                                                if row_date is not None and pd.notna(row_date) and str(row_date).strip() != "" and str(row_date).strip().lower() != 'nat' and str(row_date).strip().lower() != 'nan':
                                                    if pd.notna(row['ticker']) and pd.notna(row['amount']):
                                                        try:
                                                            date_str = pd.to_datetime(row_date).strftime('%Y-%m-%d 00:00:00')
                                                        except:
                                                            date_str = f"{row_date} 00:00:00"
                                                        new_records.append({
                                                            "date": date_str,
                                                            "ticker": str(row['ticker']),
                                                            "amount": float(row['amount']),
                                                            "portfolio_name": selected_portfolio,
                                                            "username": username
                                                        })
                                            
                                            if new_records:
                                                new_df = pd.DataFrame(new_records)
                                                curr_divs = pd.concat([other_dividends, new_df], ignore_index=True)
                                            else:
                                                curr_divs = other_dividends.reset_index(drop=True)
                                                
                                            st.session_state.dividends = curr_divs
                                            conn.update(worksheet="Dividends", data=curr_divs)
                                            conn.reset() # Invalidate GSheetsConnection cache to ensure live data load
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
            1. Select a **portfolio** in the sidebar.
            2. Add your stocks and set target weights.
            3. Run **Calculate Allocation** to get recommendations.
            """)
            st.markdown('</div>', unsafe_allow_html=True)


