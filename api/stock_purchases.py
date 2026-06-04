"""Stock purchase CRUD (add units, delete units) synced to Firestore."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pandas as pd

from api.sheets import read_dividends, read_stock_purchases, write_stock_purchases
from api import portfolio_actions
from portfolio_core import filter_master_data_by_portfolio, filter_master_data_for_user
from portfolio_data import (
    aggregate_stock_purchases,
    expand_purchases_to_units,
    infer_country_and_currency_from_ticker,
    purchases_from_dataframe,
    remove_selected_units,
    remove_unit_by_key,
    stocks_from_portfolio_df,
)

PURCHASE_COLS = [
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


def _purchases_from_sheet(
    sheet: pd.DataFrame, username: str, portfolio_name: str
) -> list[dict[str, Any]]:
    if sheet.empty or "username" not in sheet.columns:
        return []
    mask = (sheet["username"].astype(str) == str(username)) & (
        sheet["portfolio_name"].astype(str) == str(portfolio_name)
    )
    return purchases_from_dataframe(sheet.loc[mask])


def _dividend_map(
    username: str,
    portfolio_name: str,
    dividends_df: pd.DataFrame | None = None,
) -> dict[str, float]:
    df = dividends_df if dividends_df is not None else read_dividends()
    if df.empty or "ticker" not in df.columns:
        return {}
    d = df.copy()
    d["amount"] = pd.to_numeric(d["amount"], errors="coerce").fillna(0.0)
    mask = (d["username"].astype(str) == str(username)) & (
        d["portfolio_name"].astype(str) == str(portfolio_name)
    )
    return d.loc[mask].groupby("ticker")["amount"].sum().to_dict()


def _market_overrides(master: pd.DataFrame, username: str, portfolio_name: str) -> dict[str, float]:
    p_df = filter_master_data_by_portfolio(
        filter_master_data_for_user(master, username), portfolio_name
    )
    base = stocks_from_portfolio_df(p_df)
    return {str(s["name"]).upper(): float(s["current_value"]) for s in base if s.get("name")}


def _summaries_to_holdings(
    summaries: list[dict[str, Any]],
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
) -> list[dict[str, Any]]:
    p_df = filter_master_data_by_portfolio(
        filter_master_data_for_user(master, username), portfolio_name
    )
    existing = {str(s["name"]).upper(): s for s in stocks_from_portfolio_df(p_df)}
    holdings = []
    for summary in summaries:
        ticker = summary["ticker"]
        prev = existing.get(ticker, {})
        holdings.append(
            {
                "ticker": ticker,
                "current_value": summary["market_value"],
                "current_price": summary["invested_value"],
                "target_allocation": float(prev.get("target_allocation", 0) or 0),
                "tolerance": float(prev.get("tolerance", 2) or 2),
                "expense_ratio": float(prev.get("expense_ratio", 0) or 0),
                "stock_full_name": summary.get("name", ticker),
                "sector": summary.get("sector", ""),
                "industry": summary.get("industry", ""),
                "country": summary.get("country", ""),
                "currency": summary.get("currency", ""),
                "quantity": summary.get("quantity", 0),
                "average_price": summary.get("avg_price", 0),
                "dividend_yield": summary.get("div_yield", 0),
            }
        )
    return holdings


def _write_purchases_sheet(
    username: str,
    portfolio_name: str,
    purchases: list[dict[str, Any]],
    *,
    sheet_df: pd.DataFrame | None = None,
) -> None:
    sheet = sheet_df if sheet_df is not None else read_stock_purchases(use_cache=False)
    if sheet.empty or "username" not in sheet.columns:
        remaining = pd.DataFrame(columns=PURCHASE_COLS)
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
                "unit_price": float(purchase.get("unit_price", 0) or 0),
                "quantity": float(purchase.get("quantity", 0) or 0),
                "dividend_yield": float(purchase.get("dividend_yield", 0) or 0),
                "dps": float(purchase.get("dps", 0) or 0),
            }
        )
    new_rows = pd.DataFrame(rows) if rows else pd.DataFrame(columns=PURCHASE_COLS)
    updated = (
        pd.concat([remaining, new_rows], ignore_index=True)
        if not remaining.empty
        else new_rows
    )
    write_stock_purchases(updated)


def _build_payload(
    purchases: list[dict[str, Any]],
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    dividends_df: pd.DataFrame | None = None,
    *,
    market_overrides: dict[str, float] | None = None,
) -> dict[str, Any]:
    overrides = (
        market_overrides
        if market_overrides is not None
        else _market_overrides(master, username, portfolio_name)
    )
    div_map = _dividend_map(username, portfolio_name, dividends_df)
    summaries = aggregate_stock_purchases(purchases, div_map, overrides)
    p_df = filter_master_data_by_portfolio(
        filter_master_data_for_user(master, username), portfolio_name
    )
    sheet_stocks = stocks_from_portfolio_df(p_df)
    targets = {
        str(s["name"]).upper(): float(s.get("target_allocation", 0) or 0)
        for s in sheet_stocks
        if s.get("name")
    }
    tolerances = {
        str(s["name"]).upper(): float(s.get("tolerance", 2) or 2)
        for s in sheet_stocks
        if s.get("name")
    }
    total_mv = sum(s["market_value"] for s in summaries)
    for s in summaries:
        s["current_pct"] = round(
            (s["market_value"] / total_mv * 100.0) if total_mv > 0 else 0.0, 2
        )
        s["target_allocation"] = round(targets.get(s["ticker"], 0.0), 2)
        s["tolerance"] = round(tolerances.get(s["ticker"], 2.0), 2)
    units = expand_purchases_to_units(purchases)
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        by_ticker.setdefault(unit["ticker"], []).append(unit)

    return {
        "purchases": purchases,
        "units": units,
        "units_by_ticker": by_ticker,
        "summaries": summaries,
        "total_market_value": round(total_mv, 2),
        "total_invested": round(sum(s["invested_value"] for s in summaries), 2),
    }


def persist_purchases(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    purchases: list[dict[str, Any]],
    *,
    purchases_sheet: pd.DataFrame | None = None,
    dividends_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    sheet_df = purchases_sheet if purchases_sheet is not None else read_stock_purchases(
        use_cache=False
    )
    div_df = dividends_df if dividends_df is not None else read_dividends()

    _write_purchases_sheet(
        username, portfolio_name, purchases, sheet_df=sheet_df
    )
    updated_master = _sync_portfolios_from_purchases(
        master,
        username,
        portfolio_name,
        purchases,
        dividends_df=div_df,
    )
    return _build_payload(purchases, updated_master, username, portfolio_name, div_df)


def _sync_portfolios_from_purchases(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    purchases: list[dict[str, Any]],
    *,
    dividends_df: pd.DataFrame | None = None,
    market_overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    div_df = dividends_df if dividends_df is not None else read_dividends()
    overrides = (
        market_overrides
        if market_overrides is not None
        else _market_overrides(master, username, portfolio_name)
    )
    summaries = aggregate_stock_purchases(
        purchases, _dividend_map(username, portfolio_name, div_df), overrides
    )
    holdings = _summaries_to_holdings(summaries, master, username, portfolio_name)
    if not holdings:
        holdings = [
            {
                "ticker": "__PLACEHOLDER__",
                "current_value": 0.0,
                "current_price": 0.0,
                "target_allocation": 0.0,
                "tolerance": 0.0,
                "expense_ratio": 0.0,
            }
        ]
    return portfolio_actions.save_portfolio(
        master,
        username,
        portfolio_name,
        holdings=holdings,
        portfolio_type="Stocks",
    )


def update_market_values(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    market_values: dict[str, float],
) -> dict[str, Any]:
    purchases, _, div_df = _load_context(master, username, portfolio_name)
    overrides = _market_overrides(master, username, portfolio_name)
    for ticker, value in market_values.items():
        key = str(ticker).strip().upper()
        if key:
            overrides[key] = max(0.0, float(value))
    updated_master = _sync_portfolios_from_purchases(
        master,
        username,
        portfolio_name,
        purchases,
        dividends_df=div_df,
        market_overrides=overrides,
    )
    return _build_payload(
        purchases,
        updated_master,
        username,
        portfolio_name,
        div_df,
        market_overrides=overrides,
    )


def build_stock_purchases_payload(
    master: pd.DataFrame, username: str, portfolio_name: str
) -> dict[str, Any]:
    sheet_df = read_stock_purchases()
    purchases = _purchases_from_sheet(sheet_df, username, portfolio_name)
    return _build_payload(
        purchases, master, username, portfolio_name, read_dividends()
    )


def _load_context(
    master: pd.DataFrame, username: str, portfolio_name: str
) -> tuple[list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    sheet_df = read_stock_purchases(use_cache=False)
    purchases = _purchases_from_sheet(sheet_df, username, portfolio_name)
    div_df = read_dividends()
    return purchases, sheet_df, div_df


def add_purchase(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    *,
    ticker: str,
    unit_price: float,
    quantity: float,
    sector: str = "",
    industry: str = "",
    country: str = "",
    currency: str = "",
    dividend_yield: float = 0.0,
) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker is required")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if unit_price <= 0:
        raise ValueError("Price must be greater than zero")

    final_country = country.strip()
    final_currency = currency.strip()
    if not final_country or not final_currency:
        inf_country, inf_currency = infer_country_and_currency_from_ticker(ticker)
        final_country = final_country or inf_country
        final_currency = final_currency or inf_currency

    purchases, sheet_df, div_df = _load_context(master, username, portfolio_name)
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
            "dps": round(float(dividend_yield) / 100.0 * float(unit_price), 4),
        }
    )
    return persist_purchases(
        master,
        username,
        portfolio_name,
        purchases,
        purchases_sheet=sheet_df,
        dividends_df=div_df,
    )


def delete_unit(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    unit_key: str,
) -> dict[str, Any]:
    purchases, sheet_df, div_df = _load_context(master, username, portfolio_name)
    remaining = remove_unit_by_key(purchases, unit_key)
    return persist_purchases(
        master,
        username,
        portfolio_name,
        remaining,
        purchases_sheet=sheet_df,
        dividends_df=div_df,
    )


def delete_units(
    master: pd.DataFrame,
    username: str,
    portfolio_name: str,
    unit_keys: list[str],
) -> dict[str, Any]:
    purchases, sheet_df, div_df = _load_context(master, username, portfolio_name)
    remaining = remove_selected_units(purchases, set(unit_keys))
    return persist_purchases(
        master,
        username,
        portfolio_name,
        remaining,
        purchases_sheet=sheet_df,
        dividends_df=div_df,
    )
