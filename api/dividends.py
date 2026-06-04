"""Dividend records for Stocks portfolios."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from api.sheets import read_dividends, write_worksheet

MONTH_ABBR = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]


def _portfolio_dividends_df(
    df: pd.DataFrame, username: str, portfolio_name: str
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    mask = (df["username"].astype(str) == str(username)) & (
        df["portfolio_name"].astype(str) == str(portfolio_name)
    )
    sub = df.loc[mask].copy()
    if sub.empty:
        return sub
    sub["amount"] = pd.to_numeric(sub["amount"], errors="coerce").fillna(0.0)
    sub["date"] = pd.to_datetime(sub["date"], errors="coerce")
    return sub


def _monthly_comparison(
    sub: pd.DataFrame, current_year: int, *, ticker: str | None = None
) -> dict[str, Any]:
    """Grouped monthly bars: previous year + current year (all 12 months)."""
    prev_year = current_year - 1
    empty = {
        "months": MONTH_ABBR,
        "series": [
            {"year": str(prev_year), "amounts": [0.0] * 12},
            {"year": str(current_year), "amounts": [0.0] * 12},
        ],
    }
    if sub.empty:
        return empty

    filtered = sub[sub["date"].dt.year >= prev_year].copy()
    if ticker:
        filtered = filtered[filtered["ticker"].astype(str) == str(ticker)]
    if filtered.empty:
        return empty

    grouped = (
        filtered.groupby([filtered["date"].dt.year, filtered["date"].dt.month])["amount"]
        .sum()
        .to_dict()
    )

    def amounts_for(year: int) -> list[float]:
        return [
            round(float(grouped.get((year, month), 0.0)), 2)
            for month in range(1, 13)
        ]

    return {
        "months": MONTH_ABBR,
        "series": [
            {"year": str(prev_year), "amounts": amounts_for(prev_year)},
            {"year": str(current_year), "amounts": amounts_for(current_year)},
        ],
    }


def _year_totals(
    sub: pd.DataFrame, current_year: int, *, ticker: str | None = None
) -> tuple[float, float]:
    if sub.empty:
        return 0.0, 0.0
    filtered = sub[sub["date"].dt.year >= current_year - 1].copy()
    if ticker:
        filtered = filtered[filtered["ticker"].astype(str) == str(ticker)]
    if filtered.empty:
        return 0.0, 0.0
    total_current = float(
        filtered.loc[filtered["date"].dt.year == current_year, "amount"].sum()
    )
    total_previous = float(
        filtered.loc[filtered["date"].dt.year == current_year - 1, "amount"].sum()
    )
    return round(total_current, 2), round(total_previous, 2)


def list_dividends(username: str, portfolio_name: str) -> list[dict[str, Any]]:
    df = read_dividends()
    sub = _portfolio_dividends_df(df, username, portfolio_name)
    if sub.empty:
        return []
    out: list[dict[str, Any]] = []
    for _, row in sub.sort_values("date", ascending=False).iterrows():
        dt = row["date"]
        out.append(
            {
                "date": dt.strftime("%Y-%m-%d") if pd.notna(dt) else "",
                "ticker": str(row.get("ticker", "")),
                "amount": round(float(row.get("amount", 0) or 0), 2),
            }
        )
    return out


def dividend_summary(username: str, portfolio_name: str) -> dict[str, Any]:
    current_year = datetime.now().year
    df = read_dividends()
    sub = _portfolio_dividends_df(df, username, portfolio_name)
    records = list_dividends(username, portfolio_name)
    total_current, total_previous = _year_totals(sub, current_year)
    monthly_comparison = _monthly_comparison(sub, current_year)

    tickers = sorted({r["ticker"] for r in records if r["ticker"]})

    return {
        "records": records,
        "total_current_year": total_current,
        "total_previous_year": total_previous,
        "current_year": current_year,
        "monthly_comparison": monthly_comparison,
        "tickers": tickers,
    }


def add_dividend(
    username: str,
    portfolio_name: str,
    *,
    date: str,
    ticker: str,
    amount: float,
) -> dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker is required")
    if amount <= 0:
        raise ValueError("Amount must be greater than zero")

    df = read_dividends(use_cache=False)
    if df.empty:
        df = pd.DataFrame(columns=["date", "ticker", "amount", "portfolio_name", "username"])

    date_str = date.strip()
    if len(date_str) == 10:
        date_str = f"{date_str} 00:00:00"

    new_row = pd.DataFrame(
        [
            {
                "date": date_str,
                "ticker": ticker,
                "amount": round(float(amount), 2),
                "portfolio_name": portfolio_name,
                "username": username,
            }
        ]
    )
    updated = pd.concat([df, new_row], ignore_index=True)
    write_worksheet("Dividends", updated)
    return dividend_summary(username, portfolio_name)
