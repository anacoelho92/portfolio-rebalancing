"""Streamlit adapter for Firestore (replaces streamlit_gsheets.GSheetsConnection)."""

from __future__ import annotations

import pandas as pd

from api.sheets import (
    invalidate_cache,
    read_dividends,
    read_investment_log,
    read_portfolios,
    read_stock_purchases,
    write_worksheet,
)


class FirestoreConnection:
    def read(self, worksheet: str, ttl: int = 0) -> pd.DataFrame:
        use_cache = ttl > 0
        if worksheet == "Portfolios":
            return read_portfolios(use_cache=use_cache)
        if worksheet == "Dividends":
            return read_dividends(use_cache=use_cache)
        if worksheet == "StockPurchases":
            return read_stock_purchases(use_cache=use_cache)
        if worksheet == "InvestmentLog":
            return read_investment_log()
        return pd.DataFrame()

    def update(self, worksheet: str, data: pd.DataFrame) -> None:
        write_worksheet(worksheet, data)
        invalidate_cache()

    def create(self, worksheet: str, data: pd.DataFrame) -> None:
        self.update(worksheet, data)

    def reset(self) -> None:
        invalidate_cache()
