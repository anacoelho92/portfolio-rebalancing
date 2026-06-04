"""Calculate allocations, save edits, log investments, chart data."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from api.investments import build_monthly_value_invested_series, get_total_invested_from_log
from api.sheets import read_investment_log, write_portfolios, write_worksheet
from portfolio_core import (
    DEFAULT_INVESTOR_BIRTH_DATE,
    EXCLUDED_GD_TICKERS,
    PORTFOLIO_TYPE_GROWTH,
    RETIREMENT_AGE,
    SAFE_LIQUIDITY_LABEL,
    allocate_contribution,
    calculate_investor_age,
    contribution_with_uninvested_cash,
    filter_master_data_by_portfolio,
    filter_master_data_for_user,
    growth_monthly_base_from_setting,
    retirement_withdrawal_plan,
)

from api.services import portfolio_metadata
from portfolio_data import (
    growth_stocks_from_portfolio_df,
    kids_apply_targets,
    stocks_from_portfolio_df,
)


def calculate_growth_allocation(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    *,
    monthly_invest: Optional[float] = None,
    uninvested_cash: Optional[float] = None,
    safe_liquidity: Optional[float] = None,
) -> dict[str, Any]:
    user_df = filter_master_data_for_user(master, username)
    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    meta = portfolio_metadata(p_df)
    live_stocks = growth_stocks_from_portfolio_df(p_df)

    invest_setting = monthly_invest if monthly_invest is not None else meta["monthly_invest"]
    uninvested = uninvested_cash if uninvested_cash is not None else meta["uninvested_cash"]
    safe_before = safe_liquidity if safe_liquidity is not None else meta["safe_liquidity"]

    month = datetime.now().month
    base = growth_monthly_base_from_setting(invest_setting, month)
    contribution = contribution_with_uninvested_cash(base, uninvested)
    uninvested_included = round(contribution - base, 2)

    current_values = {s["name"]: s["current_value"] for s in live_stocks}
    birth = meta["investor_birth_date"]
    age = calculate_investor_age(birth)

    buys_data = allocate_contribution(
        contribution=contribution,
        age=age,
        current_values=current_values,
        min_order_size=5.0,
    )

    portfolio_targets = buys_data["portfolio_targets"]
    current_weights = buys_data["current_weights"]
    buys_map = buys_data["buys"]
    leftover_cash = buys_data["leftover_cash"]
    cash_part = buys_data["cash_part"]
    cash_split_pct = buys_data["cash_split"] * 100.0
    safe_after = safe_before + cash_part
    portfolio_value_before = buys_data["portfolio_value_before"]
    portfolio_value_after = buys_data["portfolio_value_after"]

    withdrawal_data = None
    if age >= RETIREMENT_AGE:
        withdrawal_data = retirement_withdrawal_plan(
            current_values, age, cash_buffer=safe_before
        )

    rows: list[dict[str, Any]] = []
    for stock in live_stocks:
        ticker = stock["name"]
        final_invest = buys_map.get(ticker, 0.0)
        target_pct = portfolio_targets.get(ticker, 0.0)
        target_val = portfolio_value_after * (target_pct / 100.0)
        new_val = stock["current_value"] + final_invest
        rows.append(
            {
                "stock": ticker,
                "current_value": round(stock["current_value"], 2),
                "current_pct": round(current_weights.get(ticker, 0.0), 2),
                "target_pct": round(target_pct, 2),
                "target_value": round(target_val, 2),
                "investment": round(final_invest, 2),
                "new_value": round(new_val, 2),
                "new_pct": round(
                    (new_val / portfolio_value_after * 100) if portfolio_value_after > 0 else 0,
                    2,
                ),
                "ter_pct": round(stock.get("expense_ratio", 0.0), 4),
            }
        )

    if cash_part > 0 or safe_before > 0:
        safe_pct = (
            safe_before / portfolio_value_after * 100 if portfolio_value_after > 0 else 0.0
        )
        new_safe_pct = (
            safe_after / portfolio_value_after * 100 if portfolio_value_after > 0 else 0.0
        )
        rows.append(
            {
                "stock": SAFE_LIQUIDITY_LABEL,
                "current_value": round(safe_before, 2),
                "current_pct": round(safe_pct, 2),
                "target_pct": round(cash_split_pct, 2),
                "target_value": round(
                    portfolio_value_after * (cash_split_pct / 100.0), 2
                ),
                "investment": round(cash_part, 2),
                "new_value": round(safe_after, 2),
                "new_pct": round(new_safe_pct, 2),
                "ter_pct": 0.0,
            }
        )

    custom_order = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK", SAFE_LIQUIDITY_LABEL]
    rows.sort(
        key=lambda r: custom_order.index(r["stock"])
        if r["stock"] in custom_order
        else 99
    )

    etf_rows = [r for r in rows if r["stock"] != SAFE_LIQUIDITY_LABEL]
    total_etf_investment = sum(r["investment"] for r in etf_rows)

    pie_after = [
        {"name": r["stock"], "value": r["new_value"]}
        for r in rows
        if r["stock"] not in ("EGLN.UK",) and r["new_value"] > 0
    ]
    pie_before = [
        {"name": r["stock"], "value": r["current_value"]}
        for r in rows
        if r["stock"] not in ("EGLN.UK", SAFE_LIQUIDITY_LABEL) and r["current_value"] > 0
    ]

    return {
        "portfolio_name": portfolio_name,
        "portfolio_type": PORTFOLIO_TYPE_GROWTH,
        "investor_age": age,
        "monthly_contribution": round(contribution, 2),
        "base_contribution": round(base, 2),
        "uninvested_included": uninvested_included,
        "leftover_cash": leftover_cash,
        "cash_reserve": cash_part,
        "safe_liquidity_before": round(safe_before, 2),
        "safe_liquidity_after": round(safe_after, 2),
        "total_etf_investment": round(total_etf_investment, 2),
        "portfolio_value_before": portfolio_value_before,
        "portfolio_value_after": portfolio_value_after,
        "withdrawal": withdrawal_data,
        "recommendations": rows,
        "pie_before": pie_before,
        "pie_after": pie_after,
    }


def _kids_monthly_base() -> float:
    now = datetime.now()
    if now.day >= 28:
        investment_month = 1 if now.month == 12 else now.month + 1
    else:
        investment_month = now.month
    return 100.0 if investment_month in (6, 12) else 50.0


def _allocate_standard_portfolio(
    live_stocks: list[dict[str, Any]],
    monthly_contribution: float,
) -> tuple[dict[str, float], float]:
    """Target-band rebalancing used by Kids (same logic as Streamlit non-Growth path)."""
    total_current_live = sum(s["current_value"] for s in live_stocks)
    core_target_live = sum(s["target_allocation"] for s in live_stocks)
    if abs(core_target_live - 100.0) > 0.01:
        raise ValueError(
            f"Target allocations sum to {core_target_live:.1f}% — they must sum to 100%."
        )

    remaining_investment = float(monthly_contribution)
    final_investments = {s["name"]: 0.0 for s in live_stocks}
    stocks_to_process = list(live_stocks)
    total_theoretical = total_current_live + remaining_investment

    if remaining_investment > 0 and stocks_to_process:
        stock_data_p: list[dict[str, Any]] = []
        sum_positive_deviations = 0.0

        for stock in stocks_to_process:
            current_weight = (
                (stock["current_value"] / total_current_live * 100.0)
                if total_current_live > 0
                else 0.0
            )
            target_weight = stock["target_allocation"]
            deviation = target_weight - current_weight
            min_band = target_weight - stock.get("tolerance", 0.0)
            below_min_band = current_weight < min_band
            below_target = deviation > 0

            if below_target:
                sum_positive_deviations += deviation

            target_val = total_theoretical * (target_weight / 100.0)
            gap = target_val - stock["current_value"]

            stock_data_p.append(
                {
                    "name": stock["name"],
                    "Gap": gap,
                    "stock": stock,
                    "deviation": deviation,
                    "below_min_band": below_min_band,
                    "below_target": below_target,
                    "invest": 0.0,
                    "needed_band": 0.0,
                }
            )

        total_needed_band = 0.0
        for item in stock_data_p:
            if item["below_min_band"]:
                min_band_eur = total_theoretical * (
                    (
                        item["stock"]["target_allocation"]
                        - item["stock"].get("tolerance", 0.0)
                    )
                    / 100.0
                )
                needed = max(0.0, min_band_eur - item["stock"]["current_value"])
                item["needed_band"] = needed
                total_needed_band += needed

        if total_needed_band > 0 and remaining_investment > 0:
            if total_needed_band <= remaining_investment:
                for item in stock_data_p:
                    if item["needed_band"] > 0:
                        item["invest"] += item["needed_band"]
                        remaining_investment -= item["needed_band"]
            else:
                emergency_funds = remaining_investment
                for item in stock_data_p:
                    if item["needed_band"] > 0:
                        prop_alloc = (
                            item["needed_band"] / total_needed_band
                        ) * emergency_funds
                        item["invest"] += prop_alloc
                remaining_investment = 0.0

        if remaining_investment > 0 and sum_positive_deviations > 0:
            funds_left = remaining_investment
            proportions = []
            for item in stock_data_p:
                if item["below_target"]:
                    prop_alloc = (item["deviation"] / sum_positive_deviations) * funds_left
                    max_inv = max(0.0, item["Gap"] - item["invest"])
                    ideal_invest = min(prop_alloc, max_inv)
                    proportions.append({"item": item, "ideal": ideal_invest})

            for p in proportions:
                p["item"]["invest"] += p["ideal"]
                remaining_investment -= p["ideal"]

        if remaining_investment >= 0.01:
            sorted_gaps = sorted(
                stock_data_p, key=lambda x: x["Gap"] - x["invest"], reverse=True
            )
            for g in sorted_gaps:
                if remaining_investment < 0.01:
                    break
                needed = max(0.0, g["Gap"] - g["invest"])
                if needed > 0:
                    alloc = min(remaining_investment, needed)
                    g["invest"] += alloc
                    remaining_investment -= alloc

        for item in stock_data_p:
            final_investments[item["name"]] = item["invest"]

    total_after_round = 0.0
    for ticker, invest in final_investments.items():
        rounded = float(math.floor(invest))
        final_investments[ticker] = rounded
        total_after_round += rounded

    final_remaining = monthly_contribution - total_after_round
    if final_remaining >= 1.0 and live_stocks:
        sorted_tickers = sorted(
            final_investments.keys(),
            key=lambda x: next(
                (s["target_allocation"] for s in live_stocks if s["name"] == x),
                0,
            ),
            reverse=True,
        )
        if sorted_tickers:
            final_investments[sorted_tickers[0]] += float(math.floor(final_remaining))
        leftover = monthly_contribution - sum(final_investments.values())
    else:
        leftover = final_remaining

    return final_investments, leftover


def calculate_kids_allocation(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    *,
    uninvested_cash: Optional[float] = None,
) -> dict[str, Any]:
    user_df = filter_master_data_for_user(master, username)
    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    meta = portfolio_metadata(p_df)
    stocks = stocks_from_portfolio_df(p_df)
    if meta.get("portfolio_birth_date"):
        stocks = kids_apply_targets(stocks, meta["portfolio_birth_date"])

    live_stocks = [
        {
            "name": str(s["name"]),
            "current_value": float(s["current_value"]),
            "target_allocation": float(s["target_allocation"]),
            "tolerance": float(s.get("tolerance", 2.0)),
            "expense_ratio": float(s.get("expense_ratio", 0.0)),
        }
        for s in stocks
        if str(s.get("name", "")).strip() and str(s["name"]) != "__PLACEHOLDER__"
    ]

    uninvested = (
        uninvested_cash if uninvested_cash is not None else meta["uninvested_cash"]
    )
    base = _kids_monthly_base()
    contribution = contribution_with_uninvested_cash(base, uninvested)
    uninvested_included = round(contribution - base, 2)

    invest_map, leftover = _allocate_standard_portfolio(live_stocks, contribution)

    total_current_live = sum(s["current_value"] for s in live_stocks)
    portfolio_value_after = total_current_live + contribution

    rows: list[dict[str, Any]] = []
    for stock in live_stocks:
        ticker = stock["name"]
        final_invest = invest_map.get(ticker, 0.0)
        target_val = portfolio_value_after * (stock["target_allocation"] / 100.0)
        new_val = stock["current_value"] + final_invest
        rows.append(
            {
                "stock": ticker,
                "current_value": round(stock["current_value"], 2),
                "current_pct": round(
                    (stock["current_value"] / total_current_live * 100.0)
                    if total_current_live > 0
                    else 0.0,
                    2,
                ),
                "target_pct": round(stock["target_allocation"], 2),
                "target_value": round(target_val, 2),
                "investment": round(final_invest, 2),
                "new_value": round(new_val, 2),
                "new_pct": round(
                    (new_val / portfolio_value_after * 100.0)
                    if portfolio_value_after > 0
                    else 0.0,
                    2,
                ),
                "ter_pct": round(stock.get("expense_ratio", 0.0), 4),
            }
        )

    total_investment = sum(invest_map.values())
    pie_before = [
        {"name": r["stock"], "value": r["current_value"]}
        for r in rows
        if r["current_value"] > 0
    ]
    pie_after = [
        {"name": r["stock"], "value": r["new_value"]} for r in rows if r["new_value"] > 0
    ]

    return {
        "portfolio_name": portfolio_name,
        "portfolio_type": "Kids",
        "monthly_contribution": round(contribution, 2),
        "base_contribution": round(base, 2),
        "uninvested_included": uninvested_included,
        "leftover_cash": round(leftover, 2),
        "cash_reserve": 0.0,
        "total_etf_investment": round(total_investment, 2),
        "safe_liquidity_before": 0.0,
        "safe_liquidity_after": 0.0,
        "portfolio_value_before": round(total_current_live, 2),
        "portfolio_value_after": round(portfolio_value_after, 2),
        "recommendations": rows,
        "pie_before": pie_before,
        "pie_after": pie_after,
        "investor_age": 0,
        "withdrawal": None,
    }


def save_portfolio(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    *,
    holdings: list[dict[str, Any]],
    monthly_invest: Optional[float] = None,
    uninvested_cash: Optional[float] = None,
    safe_liquidity: Optional[float] = None,
    portfolio_type: Optional[str] = None,
) -> pd.DataFrame:
    data = master.copy()
    user_df = filter_master_data_by_portfolio(
        filter_master_data_for_user(data, username), portfolio_name
    )
    meta = portfolio_metadata(user_df)
    p_type = portfolio_type or meta["portfolio_type"]

    portfolio_invest = monthly_invest if monthly_invest is not None else meta["monthly_invest"]
    portfolio_uninvested = (
        uninvested_cash if uninvested_cash is not None else meta["uninvested_cash"]
    )
    portfolio_safe = (
        safe_liquidity if safe_liquidity is not None else meta["safe_liquidity"]
    )
    if p_type != PORTFOLIO_TYPE_GROWTH:
        portfolio_safe = 0.0

    if not user_df.empty:
        fr = user_df.iloc[0]
        portfolio_use_ind = fr.get("portfolio_use_indicators", False)
        portfolio_buffett = float(fr.get("portfolio_buffett_index", 195.0))
        portfolio_birth_date = str(fr.get("portfolio_birth_date", ""))
        portfolio_uninvested_reinvested = float(
            fr.get("portfolio_uninvested_reinvested", 0.0)
        )
    else:
        portfolio_use_ind = False
        portfolio_buffett = 195.0
        portfolio_birth_date = ""
        portfolio_uninvested_reinvested = 0.0

    mask = (data["username"] == username) & (data["portfolio_name"] == portfolio_name)
    data = data[~mask]

    new_rows = []
    for h in holdings:
        ticker = str(h.get("ticker", "")).strip()
        if not ticker or ticker == "__PLACEHOLDER__":
            continue
        new_rows.append(
            {
                "username": username,
                "portfolio_name": portfolio_name,
                "stock_name": ticker,
                "current_value": float(h.get("current_value", 0)),
                "target_allocation": float(h.get("target_allocation", 0)),
                "current_price": float(h.get("current_price", 0)),
                "tolerance": float(h.get("tolerance", 2)),
                "expense_ratio": float(h.get("expense_ratio", 0)),
                "portfolio_monthly_invest": portfolio_invest,
                "portfolio_use_indicators": portfolio_use_ind,
                "portfolio_buffett_index": portfolio_buffett,
                "portfolio_birth_date": portfolio_birth_date,
                "portfolio_uninvested_cash": portfolio_uninvested,
                "portfolio_safe_liquidity": portfolio_safe,
                "portfolio_uninvested_reinvested": portfolio_uninvested_reinvested,
                "investor_birth_date": DEFAULT_INVESTOR_BIRTH_DATE,
                "portfolio_type": p_type,
                "stock_full_name": h.get("stock_full_name", ticker),
                "sector": h.get("sector", ""),
                "industry": h.get("industry", ""),
                "country": h.get("country", ""),
                "currency": h.get("currency", ""),
                "quantity": float(h.get("quantity", 0)),
                "average_price": float(h.get("average_price", 0)),
                "dividend_yield": float(h.get("dividend_yield", 0)),
            }
        )

    if not new_rows:
        new_rows.append(
            {
                "username": username,
                "portfolio_name": portfolio_name,
                "stock_name": "__PLACEHOLDER__",
                "current_value": 0.0,
                "target_allocation": 0.0,
                "current_price": 0.0,
                "portfolio_monthly_invest": portfolio_invest,
                "portfolio_use_indicators": portfolio_use_ind,
                "portfolio_buffett_index": portfolio_buffett,
                "portfolio_birth_date": portfolio_birth_date,
                "portfolio_uninvested_cash": portfolio_uninvested,
                "portfolio_safe_liquidity": portfolio_safe,
                "portfolio_uninvested_reinvested": portfolio_uninvested_reinvested,
                "investor_birth_date": DEFAULT_INVESTOR_BIRTH_DATE,
                "portfolio_type": p_type,
                "stock_full_name": "",
                "sector": "",
                "industry": "",
                "country": "",
                "currency": "",
                "quantity": 0.0,
                "average_price": 0.0,
                "dividend_yield": 0.0,
                "tolerance": 0.0,
                "expense_ratio": 0.0,
            }
        )

    updated = pd.concat([data, pd.DataFrame(new_rows)], ignore_index=True)
    return write_portfolios(updated)


def log_growth_investment(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    calc: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    if calc is None:
        calc = calculate_growth_allocation(master, username, portfolio_name)

    rows = calc["recommendations"]
    df = pd.DataFrame(
        [
            {
                "Stock": r["stock"],
                "Current Value": r["current_value"],
                "Current %": r["current_pct"],
                "Target %": r["target_pct"],
                "Target Value": r["target_value"],
                "Investment": r["investment"],
                "New Value": r["new_value"],
                "New %": r["new_pct"],
            }
            for r in rows
        ]
    )
    df = df[~df["Stock"].astype(str).str.upper().isin(EXCLUDED_GD_TICKERS)]

    log_rows = df.copy()
    log_rows["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_rows["username"] = username
    log_rows["portfolio_name"] = portfolio_name
    cols = [
        "timestamp",
        "username",
        "portfolio_name",
        "Stock",
        "Current Value",
        "Current %",
        "Target %",
        "Target Value",
        "Investment",
        "New Value",
        "New %",
    ]
    log_df = log_rows[cols]

    existing = read_investment_log()
    new_history = (
        pd.concat([existing, log_df], ignore_index=True)
        if existing is not None and not existing.empty
        else log_df
    )
    write_worksheet("InvestmentLog", new_history)

    master_data = master.copy()
    uninvested_included = float(calc.get("uninvested_included", 0))
    safe_after = float(calc.get("safe_liquidity_after", 0))

    for _, row in df.iterrows():
        stock_ticker = row["Stock"]
        if stock_ticker == SAFE_LIQUIDITY_LABEL:
            continue
        new_val = row["New Value"]
        mask = (
            (master_data["username"] == username)
            & (master_data["portfolio_name"] == portfolio_name)
            & (master_data["stock_name"] == stock_ticker)
        )
        if mask.any():
            master_data.loc[mask, "current_value"] = new_val

    portfolio_mask = (master_data["username"] == username) & (
        master_data["portfolio_name"] == portfolio_name
    )
    if portfolio_mask.any():
        master_data.loc[portfolio_mask, "portfolio_safe_liquidity"] = safe_after
        if uninvested_included > 0:
            p_df = master_data.loc[portfolio_mask]
            current_uninv = float(p_df["portfolio_uninvested_cash"].iloc[0])
            current_reinv = float(p_df["portfolio_uninvested_reinvested"].iloc[0])
            new_uninv = max(0.0, current_uninv - uninvested_included)
            new_reinv = current_reinv + uninvested_included
            master_data.loc[portfolio_mask, "portfolio_uninvested_cash"] = new_uninv
            master_data.loc[portfolio_mask, "portfolio_uninvested_reinvested"] = new_reinv

    write_portfolios(master_data)
    return {"status": "ok", "message": "Logged and portfolio updated"}


def build_chart_payload(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
) -> dict[str, Any]:
    user_df = filter_master_data_for_user(master, username)
    p_df = filter_master_data_by_portfolio(user_df, portfolio_name)
    meta = portfolio_metadata(p_df)
    from api.services import build_portfolio_summary

    summary = build_portfolio_summary(master, username, portfolio_name)
    chart_total_value = summary["total_value"]
    if meta["portfolio_type"] == PORTFOLIO_TYPE_GROWTH:
        chart_total_value += meta["safe_liquidity"]

    log = read_investment_log()
    chart_total_invested = get_total_invested_from_log(
        log,
        username,
        portfolio_name,
        meta["uninvested_cash"],
        float(p_df["portfolio_uninvested_reinvested"].iloc[0])
        if not p_df.empty and "portfolio_uninvested_reinvested" in p_df.columns
        else 0.0,
    )

    ts_df = build_monthly_value_invested_series(
        log,
        username,
        portfolio_name,
        current_total_value=chart_total_value,
        current_total_invested=chart_total_invested,
    )

    series = []
    if not ts_df.empty:
        for _, row in ts_df.iterrows():
            series.append(
                {
                    "month": str(row.get("month_label", "")),
                    "total_value": float(row.get("total_value", 0) or 0),
                    "total_invested": float(row.get("total_invested", 0) or 0)
                    if pd.notna(row.get("total_invested"))
                    else None,
                }
            )

    holdings = summary.get("holdings", [])
    holdings_pie = [
        {"name": h["ticker"], "value": h["current_value"]}
        for h in holdings
        if h.get("current_value", 0) > 0
    ]

    def _group_pie(field: str, *, skip_empty: bool = False) -> list[dict[str, Any]]:
        groups: dict[str, float] = {}
        for h in holdings:
            val = float(h.get("current_value", 0) or 0)
            if val <= 0:
                continue
            key = str(h.get(field, "") or "").strip()
            if skip_empty and not key:
                continue
            label = key or "Unknown"
            groups[label] = groups.get(label, 0.0) + val
        return [{"name": k, "value": round(v, 2)} for k, v in sorted(groups.items())]

    payload: dict[str, Any] = {
        "time_series": series,
        "holdings_pie": holdings_pie,
        "total_value": round(chart_total_value, 2),
        "total_invested": chart_total_invested,
    }
    if meta["portfolio_type"] == "Stocks":
        payload["distributions"] = {
            "by_stock": holdings_pie,
            "by_sector": _group_pie("sector", skip_empty=True),
            "by_industry": _group_pie("industry", skip_empty=True),
            "by_country": _group_pie("country", skip_empty=True),
        }
    return payload
