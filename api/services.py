"""Portfolio aggregation for API responses (aligned with Streamlit)."""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from api.investments import get_total_invested_from_log
from api.sheets import read_dividends, read_investment_log, read_stock_purchases
from portfolio_core import (
    BASE_CONTRIBUTION,
    DEFAULT_INVESTOR_BIRTH_DATE,
    GLOBAL_OVERVIEW_LABEL,
    PORTFOLIO_TYPE_GROWTH,
    allocate_contribution,
    calculate_investor_age,
    contribution_with_uninvested_cash,
    filter_master_data_by_portfolio,
    filter_master_data_for_user,
    growth_monthly_base_from_setting,
    growth_targets_by_ticker,
    normalize_portfolio_type,
)
from portfolio_data import (
    global_breakdown,
    global_total_value,
    growth_stocks_from_portfolio_df,
    kids_apply_targets,
    portfolio_total_from_stocks,
    stocks_from_portfolio_df,
    stocks_portfolio_holdings,
    stocks_to_holdings,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def portfolio_names_for_user(df: pd.DataFrame, username: str) -> list[str]:
    user_df = filter_master_data_for_user(df, username)
    if user_df.empty:
        return []
    return sorted(
        {
            str(n)
            for n in user_df["portfolio_name"].unique()
            if str(n).strip() and str(n) != "__PLACEHOLDER__"
        }
    )


def portfolio_type_for_name(
    master: pd.DataFrame, username: str, portfolio_name: str
) -> str:
    """Portfolio type from master sheet only (no StockPurchases/Dividends reads)."""
    user_df = filter_master_data_for_user(master, username)
    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    return portfolio_metadata(p_df)["portfolio_type"]


def portfolio_metadata(portfolio_df: pd.DataFrame) -> dict[str, Any]:
    if portfolio_df.empty:
        return {
            "portfolio_type": PORTFOLIO_TYPE_GROWTH,
            "monthly_invest": BASE_CONTRIBUTION,
            "uninvested_cash": 0.0,
            "safe_liquidity": 0.0,
            "investor_birth_date": DEFAULT_INVESTOR_BIRTH_DATE,
            "portfolio_birth_date": "",
        }
    row = portfolio_df.iloc[0]
    return {
        "portfolio_type": normalize_portfolio_type(str(row.get("portfolio_type", "Other"))),
        "monthly_invest": _safe_float(row.get("portfolio_monthly_invest"), BASE_CONTRIBUTION),
        "uninvested_cash": _safe_float(row.get("portfolio_uninvested_cash")),
        "safe_liquidity": _safe_float(row.get("portfolio_safe_liquidity")),
        "investor_birth_date": str(row.get("investor_birth_date") or DEFAULT_INVESTOR_BIRTH_DATE),
        "portfolio_birth_date": str(row.get("portfolio_birth_date") or ""),
    }


def _load_stocks_for_portfolio(
    p_df: pd.DataFrame,
    meta: dict[str, Any],
    username: str,
    portfolio_name: str,
) -> list[dict[str, Any]]:
    p_type = meta["portfolio_type"]
    if p_type == PORTFOLIO_TYPE_GROWTH:
        return growth_stocks_from_portfolio_df(p_df)
    if p_type == "Stocks":
        purchases_df = read_stock_purchases()
        dividends_df = read_dividends()
        return stocks_portfolio_holdings(
            p_df, purchases_df, dividends_df, username, portfolio_name
        )
    stocks = stocks_from_portfolio_df(p_df)
    if p_type == "Kids" and meta.get("portfolio_birth_date"):
        stocks = kids_apply_targets(stocks, meta["portfolio_birth_date"])
    return stocks_to_holdings(stocks) if p_type != "Stocks" else stocks


def _portfolio_total_quick(
    user_df: pd.DataFrame,
    portfolio_name: str,
) -> tuple[float, str]:
    """Fast total for list/home — sheet rows only (no StockPurchases aggregation)."""
    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    meta = portfolio_metadata(p_df)
    p_type = meta["portfolio_type"]

    if p_type == PORTFOLIO_TYPE_GROWTH:
        stocks = growth_stocks_from_portfolio_df(p_df)
    else:
        stocks = stocks_from_portfolio_df(p_df)
        if p_type == "Kids" and meta.get("portfolio_birth_date"):
            stocks = kids_apply_targets(stocks, meta["portfolio_birth_date"])

    holdings = [{"current_value": _safe_float(s.get("current_value"))} for s in stocks]
    total = portfolio_total_from_stocks(holdings, p_type)
    return round(total, 2), p_type


def build_home_payload(master: pd.DataFrame, username: str) -> dict[str, Any]:
    """Single read of master data for home screen (overview + portfolio list)."""
    user_df = filter_master_data_for_user(master, username)
    names = portfolio_names_for_user(master, username)
    total = global_total_value(user_df)
    overview: dict[str, Any] = {
        "name": GLOBAL_OVERVIEW_LABEL,
        "portfolio_type": "Overview",
        "total_value": round(total, 2),
        "holdings": [],
        "breakdown": global_breakdown(user_df),
    }
    items = [
        {
            "name": GLOBAL_OVERVIEW_LABEL,
            "portfolio_type": "Overview",
            "total_value": overview["total_value"],
        }
    ]
    for name in names:
        value, p_type = _portfolio_total_quick(user_df, name)
        items.append(
            {
                "name": name,
                "portfolio_type": p_type,
                "total_value": value,
            }
        )
    return {
        "total_value": round(total, 2),
        "portfolios": items,
        "overview": overview,
    }


def build_portfolio_summary(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
) -> dict[str, Any]:
    user_df = filter_master_data_for_user(master, username)

    if portfolio_name == GLOBAL_OVERVIEW_LABEL:
        return {
            "name": GLOBAL_OVERVIEW_LABEL,
            "portfolio_type": "Overview",
            "total_value": global_total_value(user_df),
            "holdings": [],
            "breakdown": global_breakdown(user_df),
        }

    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    meta = portfolio_metadata(p_df)
    p_type = meta["portfolio_type"]

    if p_type == PORTFOLIO_TYPE_GROWTH:
        stocks = growth_stocks_from_portfolio_df(p_df)
        holdings = stocks_to_holdings(stocks)
    elif p_type == "Stocks":
        holdings = _load_stocks_for_portfolio(p_df, meta, username, portfolio_name)
    else:
        stocks = stocks_from_portfolio_df(p_df)
        if p_type == "Kids" and meta.get("portfolio_birth_date"):
            stocks = kids_apply_targets(stocks, meta["portfolio_birth_date"])
        holdings = stocks_to_holdings(stocks)

    total_value = portfolio_total_from_stocks(
        [{"current_value": h["current_value"]} for h in holdings], p_type
    )
    weighted_ter = 0.0
    if total_value > 0:
        weighted_ter = sum(
            h["current_value"] / total_value * h["expense_ratio"] for h in holdings
        )
    target_sum = sum(h["target_allocation"] for h in holdings)

    active = [h for h in holdings if str(h.get("ticker", "")) != "__PLACEHOLDER__"]
    holdings_count = len(active)

    result: dict[str, Any] = {
        "name": portfolio_name,
        "portfolio_type": p_type,
        "total_value": total_value,
        "target_sum": round(target_sum, 2),
        "weighted_ter": round(weighted_ter, 2),
        "monthly_invest": meta["monthly_invest"],
        "uninvested_cash": meta["uninvested_cash"],
        "safe_liquidity": meta["safe_liquidity"],
        "holdings": holdings,
        "holdings_count": holdings_count,
    }

    if p_type == "Stocks":
        total_invested = sum(_safe_float(h.get("total_invested")) for h in active)
        profit = total_value - total_invested
        profit_pct = (profit / total_invested * 100.0) if total_invested > 0 else 0.0
        unique_sectors = {str(h.get("sector", "")).strip() for h in active if h.get("sector")}
        volumes_count = sum(_safe_float(h.get("quantity")) for h in active)
        weighted_div_yield_sum = sum(
            _safe_float(h.get("current_value")) * _safe_float(h.get("dividend_yield"))
            for h in active
        )
        portfolio_div_yield = (
            (weighted_div_yield_sum / total_value) if total_value > 0 else 0.0
        )
        portfolio_yoc = (
            (weighted_div_yield_sum / total_invested) if total_invested > 0 else 0.0
        )
        result.update(
            {
                "total_invested": round(total_invested, 2),
                "profit": round(profit, 2),
                "profit_pct": round(profit_pct, 2),
                "volumes_count": round(volumes_count),
                "num_sectors": len(unique_sectors),
                "portfolio_div_yield": round(portfolio_div_yield, 2),
                "portfolio_yoc": round(portfolio_yoc, 2),
            }
        )
    elif p_type in (PORTFOLIO_TYPE_GROWTH, "Kids"):
        log = read_investment_log()
        result["total_invested"] = get_total_invested_from_log(
            log,
            username,
            portfolio_name,
            meta["uninvested_cash"],
        )

    return result


def build_growth_allocation(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
) -> dict[str, Any]:
    user_df = filter_master_data_for_user(master, username)
    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    meta = portfolio_metadata(p_df)
    stocks = growth_stocks_from_portfolio_df(p_df)

    current_values = {s["name"]: s["current_value"] for s in stocks}
    birth = meta["investor_birth_date"]
    age = calculate_investor_age(birth)
    month = date.today().month
    base = growth_monthly_base_from_setting(meta["monthly_invest"], month)
    contribution = contribution_with_uninvested_cash(base, meta["uninvested_cash"])
    plan = allocate_contribution(contribution, age, current_values)
    plan["age"] = age
    plan["age_targets"] = growth_targets_by_ticker(age)
    plan["portfolio_name"] = portfolio_name
    return plan
