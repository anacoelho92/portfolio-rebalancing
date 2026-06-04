"""Shared portfolio business logic (Streamlit, API, and mobile)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd

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
GROWTH_DIVIDENDS_TICKERS = GROWTH_ETF_TICKERS
REMOVED_GD_TICKERS = {"WTEQ.DE", "VDIV.DE", "JMT.PT", "EDP.PT"}
SAFE_LIQUIDITY_LABEL = "Safe Liquidity"
GLOBAL_OVERVIEW_LABEL = "🌍 Global Overview"
DEFAULT_INVESTOR_BIRTH_DATE = "1992-01-01"
DELETE_ICON = ":material/delete:"

KIDS_ETF_VWCE = "VWCE.DE"
KIDS_ETF_VAGF = "VAGF.DE"
KIDS_ETF_TICKERS = [KIDS_ETF_VWCE, KIDS_ETF_VAGF]
KIDS_GLIDE_START_AGE = 12
KIDS_GLIDE_FINAL_AGE = 20

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


def round_weights(weights: Dict[str, float], decimals: int = 2) -> Dict[str, float]:
    return {asset: round(weight, decimals) for asset, weight in weights.items()}


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


def apply_cents_to_largest_investment(
    investments: Dict[str, float],
    total_budget: float,
) -> Dict[str, float]:
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


@dataclass
class KidsTargetAllocation:
    age: int
    vwce: float
    vagf: float


def target_date_allocation(age: int) -> KidsTargetAllocation:
    """
    Target-Date glide path for Kids portfolios:

    0-12: 100% VWCE / 0% VAGF
    13-20: linear transition to 70% VWCE / 30% VAGF
    20+: 70% VWCE / 30% VAGF
    """
    age = max(0, int(age))

    if age <= KIDS_GLIDE_START_AGE:
        vwce, vagf = 100.0, 0.0
    elif age >= KIDS_GLIDE_FINAL_AGE:
        vwce, vagf = 70.0, 30.0
    else:
        progress = (age - KIDS_GLIDE_START_AGE) / (
            KIDS_GLIDE_FINAL_AGE - KIDS_GLIDE_START_AGE
        )
        vwce = 100.0 - (30.0 * progress)
        vagf = 30.0 * progress

    return KidsTargetAllocation(
        age=age,
        vwce=round(vwce, 1),
        vagf=round(vagf, 1),
    )


def kids_age_from_birth_date(birth_date_str: str) -> Optional[int]:
    if not birth_date_str or not isinstance(birth_date_str, str):
        return None
    try:
        birth_date = datetime.strptime(birth_date_str.strip()[:10], "%Y-%m-%d").date()
        today = date.today()
        return today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )
    except (ValueError, TypeError):
        return None


def calculate_kids_targets(birth_date_str: str) -> Optional[Dict[str, float]]:
    age = kids_age_from_birth_date(birth_date_str)
    if age is None:
        return None
    alloc = target_date_allocation(age)
    return {KIDS_ETF_VWCE: alloc.vwce, KIDS_ETF_VAGF: alloc.vagf}


def kids_glide_path_summary(birth_date_str: str) -> Optional[Dict[str, Any]]:
    age = kids_age_from_birth_date(birth_date_str)
    if age is None:
        return None
    alloc = target_date_allocation(age)
    return {
        "age": alloc.age,
        "vwce_pct": alloc.vwce,
        "vagf_pct": alloc.vagf,
        "targets": {KIDS_ETF_VWCE: alloc.vwce, KIDS_ETF_VAGF: alloc.vagf},
    }


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


def filter_growth_dividends_stocks(stocks: List[dict]) -> List[dict]:
    return [
        s for s in stocks
        if str(s.get("name", "")).upper() not in EXCLUDED_GD_TICKERS
    ]


def growth_monthly_base_from_setting(monthly_invest: float, month: int) -> float:
    base = max(0.0, float(monthly_invest))
    if month in (6, 12):
        return round(base * 2, 2)
    return round(base, 2)


def contribution_with_uninvested_cash(base_contribution: float, uninvested_cash: float) -> float:
    return round(float(base_contribution) + max(0.0, float(uninvested_cash)), 2)


def allocate_contribution(
    contribution: float,
    age: int,
    current_values: Dict[str, float],
    min_order_size: float = 5.0,
) -> Dict[str, Any]:
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
