"""Load and aggregate portfolio data the same way as app.py (Streamlit)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd

from portfolio_core import (
    DEFAULT_INVESTOR_BIRTH_DATE,
    EXCLUDED_GD_TICKERS,
    GROWTH_DIVIDENDS_TICKERS,
    PORTFOLIO_TYPE_GROWTH,
    RETIRED_TICKERS,
    calculate_investor_age,
    calculate_kids_targets,
    calculate_portfolio_targets,
    filter_growth_dividends_stocks,
    get_tolerance_for_ticker,
    normalize_portfolio_type,
)

GROWTH_TICKER_MAP = {
    "EGNL.UK": "EGLN.UK",
    "EGLN.UK": "EGLN.UK",
}

GROWTH_TICKERS_SET = {"SPYL.DE", "IXUA.DE", "VFEA.DE"}
DIVIDEND_TICKERS_SET = {"WTEQ.DE", "VDIV.DE", "EDP.PT", "JMT.PT"}
GOLD_TICKERS_SET = {"EGLN.UK", "EGNL.UK"}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def assign_global_portfolio_label(row: pd.Series) -> str:
    ticker = str(row["stock_name"]).upper().strip()
    p_type = normalize_portfolio_type(str(row.get("portfolio_type", "")).strip())
    p_name = str(row["portfolio_name"]).strip()

    if ticker in RETIRED_TICKERS:
        return p_name
    if ticker in GOLD_TICKERS_SET:
        return "Gold"
    if p_type == "Kids":
        return p_name
    if p_type == PORTFOLIO_TYPE_GROWTH or "growth" in p_name.lower():
        if ticker in GROWTH_TICKERS_SET:
            return "Growth"
        if ticker in DIVIDEND_TICKERS_SET:
            return "Dividends"
    return p_name


def global_total_value(user_df: pd.DataFrame) -> float:
    if user_df.empty:
        return 0.0
    valid = user_df[user_df["stock_name"] != "__PLACEHOLDER__"].copy()
    if valid.empty:
        return 0.0
    valid = valid.copy()
    valid["portfolio_name"] = valid.apply(assign_global_portfolio_label, axis=1)
    merged = valid.groupby("portfolio_name")["current_value"].sum()
    positive = merged[merged > 0]
    return round(float(positive.sum()), 2)


def global_breakdown(user_df: pd.DataFrame) -> list[dict[str, Any]]:
    if user_df.empty:
        return []
    valid = user_df[user_df["stock_name"] != "__PLACEHOLDER__"].copy()
    valid["portfolio_name"] = valid.apply(assign_global_portfolio_label, axis=1)
    merged = (
        valid.groupby("portfolio_name")["current_value"]
        .sum()
        .reset_index()
        .rename(columns={"current_value": "total_value"})
    )
    merged = merged[merged["total_value"] > 0].sort_values("portfolio_name")
    return [
        {"name": str(r["portfolio_name"]), "total_value": round(float(r["total_value"]), 2)}
        for _, r in merged.iterrows()
    ]


def growth_stocks_from_portfolio_df(portfolio_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Mirror Streamlit Growth init: map tickers, aggregate duplicates, fill required ETFs."""
    if portfolio_df.empty:
        portfolio_df = pd.DataFrame()
    rows = portfolio_df[portfolio_df["stock_name"] != "__PLACEHOLDER__"] if not portfolio_df.empty else portfolio_df

    aggregated: dict[str, dict[str, Any]] = {}
    for _, row in rows.iterrows():
        raw_name = str(row["stock_name"])
        mapped = GROWTH_TICKER_MAP.get(raw_name, raw_name)
        if mapped.upper() in EXCLUDED_GD_TICKERS:
            continue
        if mapped not in aggregated:
            aggregated[mapped] = {
                "name": mapped,
                "current_value": 0.0,
                "target_allocation": 0.0,
                "tolerance": get_tolerance_for_ticker(mapped),
                "expense_ratio": _safe_float(row.get("expense_ratio")),
                "sector": str(row.get("sector") or ""),
                "industry": str(row.get("industry") or ""),
            }
        rec = aggregated[mapped]
        rec["current_value"] += _safe_float(row.get("current_value"))
        if rec["expense_ratio"] == 0.0 and _safe_float(row.get("expense_ratio")) > 0:
            rec["expense_ratio"] = _safe_float(row.get("expense_ratio"))

    stocks = filter_growth_dividends_stocks(list(aggregated.values()))
    existing = {s["name"] for s in stocks}
    for ticker in GROWTH_DIVIDENDS_TICKERS:
        if ticker not in existing:
            stocks.append(
                {
                    "name": ticker,
                    "current_value": 0.0,
                    "target_allocation": 0.0,
                    "tolerance": get_tolerance_for_ticker(ticker),
                    "expense_ratio": 0.0,
                    "sector": "",
                    "industry": "",
                }
            )

    age = calculate_investor_age(DEFAULT_INVESTOR_BIRTH_DATE)
    try:
        targets_data = calculate_portfolio_targets(age)
        unified_targets = targets_data["targets"]
    except ValueError:
        unified_targets = {}

    for stock in stocks:
        ticker = stock["name"]
        if ticker in unified_targets:
            stock["target_allocation"] = unified_targets[ticker]
            stock["tolerance"] = get_tolerance_for_ticker(ticker, unified_targets)
        else:
            stock["target_allocation"] = 0.0
            stock["tolerance"] = get_tolerance_for_ticker(ticker, unified_targets)

    custom_order = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"]
    stocks.sort(
        key=lambda x: custom_order.index(x["name"]) if x["name"] in custom_order else 99
    )
    return stocks


def stocks_from_portfolio_df(portfolio_df: pd.DataFrame) -> list[dict[str, Any]]:
    if portfolio_df.empty:
        return []
    out = []
    for _, row in portfolio_df.iterrows():
        if str(row["stock_name"]) == "__PLACEHOLDER__":
            continue
        out.append(
            {
                "name": str(row["stock_name"]),
                "current_value": _safe_float(row.get("current_value")),
                "target_allocation": _safe_float(row.get("target_allocation")),
                "tolerance": _safe_float(row.get("tolerance"), 2.0),
                "expense_ratio": _safe_float(row.get("expense_ratio")),
                "sector": str(row.get("sector") or ""),
                "industry": str(row.get("industry") or ""),
                "quantity": _safe_float(row.get("quantity")),
                "average_price": _safe_float(row.get("average_price")),
            }
        )
    return out


def purchase_dividend_yield(purchase: dict) -> float:
    return _safe_float(purchase.get("dividend_yield"))


def purchase_dps(purchase: dict) -> float:
    unit_price = _safe_float(purchase.get("unit_price"))
    if unit_price <= 0:
        return 0.0
    return purchase_dividend_yield(purchase) / 100.0 * unit_price


def purchases_from_dataframe(df: pd.DataFrame) -> list[dict]:
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
                "unit_price": _safe_float(row.get("unit_price")),
                "quantity": _safe_float(row.get("quantity")),
                "dividend_yield": _safe_float(row.get("dividend_yield")),
                "dps": _safe_float(row.get("dps")),
            }
        )
    return purchases


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


def expand_purchases_to_units(purchases: list[dict]) -> list[dict]:
    units: list[dict] = []
    for purchase in purchases:
        qty = _safe_float(purchase.get("quantity"))
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
                        "price": _safe_float(purchase.get("unit_price")),
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
                    "price": _safe_float(purchase.get("unit_price")),
                    "currency": purchase.get("currency", ""),
                    "dividend_yield": purchase_dividend_yield(purchase),
                    "fractional": True,
                    "display_qty": qty,
                }
            )
    return units


def remove_purchase_unit(
    purchases: list[dict], purchase_id: str, unit_index: int
) -> list[dict]:
    updated: list[dict] = []
    for purchase in purchases:
        if str(purchase.get("id")) != str(purchase_id):
            updated.append(purchase)
            continue
        qty = _safe_float(purchase.get("quantity"))
        whole = int(round(qty))
        if abs(qty - whole) >= 1e-6 or whole < 1:
            continue
        new_qty = whole - 1
        if new_qty > 0:
            copy_p = purchase.copy()
            copy_p["quantity"] = float(new_qty)
            updated.append(copy_p)
    return updated


def remove_unit_by_key(purchases: list[dict], unit_key: str) -> list[dict]:
    key_str = str(unit_key)
    if key_str.endswith("#frac"):
        purchase_id = key_str[: -len("#frac")]
        return [p for p in purchases if str(p.get("id")) != purchase_id]
    if "#" not in key_str:
        return purchases
    purchase_id = key_str.rsplit("#", 1)[0]
    return remove_purchase_unit(purchases, purchase_id, 0)


def remove_selected_units(purchases: list[dict], unit_keys: set[str]) -> list[dict]:
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

    removals_by_purchase: dict[str, int] = {}
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


def aggregate_stock_purchases(
    purchases: list[dict],
    dividend_map: dict[str, float],
    market_overrides: dict[str, float],
) -> list[dict]:
    buckets: dict[str, dict] = {}
    for purchase in purchases:
        ticker = str(purchase.get("ticker", "")).strip().upper()
        if not ticker:
            continue
        qty = _safe_float(purchase.get("quantity"))
        unit_price = _safe_float(purchase.get("unit_price"))
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
        div_yield = (
            (weighted_dps / price_per_share * 100.0) if price_per_share > 0 else 0.0
        )
        yoc = (
            (div_yield / 100.0) * (market_value / invested) * 100.0 if invested > 0 else 0.0
        )
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


def stocks_portfolio_holdings(
    portfolio_df: pd.DataFrame,
    purchases_df: pd.DataFrame,
    dividends_df: pd.DataFrame,
    username: str,
    portfolio_name: str,
) -> list[dict[str, Any]]:
    """Stocks portfolios: values from purchases + market overrides (like Streamlit)."""
    base_stocks = stocks_from_portfolio_df(portfolio_df)
    market_overrides = {
        str(s["name"]).upper(): float(s["current_value"])
        for s in base_stocks
        if s.get("name")
    }

    if purchases_df.empty or "username" not in purchases_df.columns:
        purchases = []
    else:
        mask = (purchases_df["username"].astype(str) == str(username)) & (
            purchases_df["portfolio_name"].astype(str) == str(portfolio_name)
        )
        purchases = purchases_from_dataframe(purchases_df.loc[mask])

    if not purchases and base_stocks:
        for s in base_stocks:
            purchases.append(
                {
                    "id": str(uuid4()),
                    "ticker": str(s["name"]).upper(),
                    "name": s["name"],
                    "sector": s.get("sector", ""),
                    "industry": s.get("industry", ""),
                    "country": "",
                    "currency": "",
                    "unit_price": s.get("average_price", 0) or 0,
                    "quantity": s.get("quantity", 0) or 0,
                    "dividend_yield": 0.0,
                    "dps": 0.0,
                }
            )

    dividend_map: dict[str, float] = {}
    if not dividends_df.empty and "ticker" in dividends_df.columns:
        d = dividends_df.copy()
        d["amount"] = pd.to_numeric(d["amount"], errors="coerce").fillna(0.0)
        mask = (d["username"].astype(str) == str(username)) & (
            d["portfolio_name"].astype(str) == str(portfolio_name)
        )
        dividend_map = d.loc[mask].groupby("ticker")["amount"].sum().to_dict()

    summaries = aggregate_stock_purchases(purchases, dividend_map, market_overrides)
    existing = {s["name"]: s for s in base_stocks}
    holdings = []
    for summary in summaries:
        ticker = summary["ticker"]
        prev = existing.get(ticker, existing.get(summary["name"], {}))
        holdings.append(
            {
                "ticker": ticker,
                "current_value": summary["market_value"],
                "current_price": summary["invested_value"],
                "target_allocation": _safe_float(prev.get("target_allocation")),
                "tolerance": _safe_float(prev.get("tolerance"), 2.0),
                "expense_ratio": _safe_float(prev.get("expense_ratio")),
                "stock_full_name": summary.get("name", ticker),
                "sector": summary.get("sector", ""),
                "industry": summary.get("industry", ""),
                "country": summary.get("country", ""),
                "currency": summary.get("currency", ""),
                "quantity": summary.get("quantity", 0),
                "average_price": summary.get("avg_price", 0),
                "dividend_yield": summary.get("div_yield", 0),
                "total_invested": summary.get("invested_value", 0),
            }
        )
    return holdings


def kids_apply_targets(stocks: list[dict[str, Any]], birth_date: str) -> list[dict[str, Any]]:
    targets = calculate_kids_targets(birth_date)
    if not targets:
        return stocks
    for stock in stocks:
        key = str(stock.get("name", "")).upper()
        if key in targets:
            stock["target_allocation"] = targets[key]
    return stocks


def stocks_to_holdings(stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": s["name"],
            "current_value": round(_safe_float(s.get("current_value")), 2),
            "target_allocation": round(_safe_float(s.get("target_allocation")), 2),
            "tolerance": round(_safe_float(s.get("tolerance"), 2.0), 2),
            "expense_ratio": round(_safe_float(s.get("expense_ratio")), 4),
            "sector": s.get("sector", ""),
            "industry": s.get("industry", ""),
            "quantity": _safe_float(s.get("quantity")),
            "total_invested": round(_safe_float(s.get("total_invested")), 2),
        }
        for s in stocks
    ]


def portfolio_total_from_stocks(stocks: list[dict[str, Any]], portfolio_type: str) -> float:
    return round(sum(_safe_float(s.get("current_value")) for s in stocks), 2)
