"""Investment log and chart series (no Streamlit)."""

from __future__ import annotations

from typing import Optional

import pandas as pd


def get_total_invested_from_log(
    log: pd.DataFrame,
    username: str,
    portfolio_name: str,
    uninvested_cash: float = 0.0,
    uninvested_reinvested: float = 0.0,
) -> float:
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
    return round(
        max(0.0, logged_sum - max(0.0, uninvested_cash) - max(0.0, uninvested_reinvested)),
        2,
    )


def build_monthly_value_invested_series(
    log: pd.DataFrame,
    username: str,
    portfolio_name: str,
    current_total_value: Optional[float] = None,
    current_total_invested: Optional[float] = None,
) -> pd.DataFrame:
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
                        pd.to_numeric(month_df["Investment"], errors="coerce").fillna(0).sum()
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
                        total_value = (
                            float(
                                pd.to_numeric(snapshot["New Value"], errors="coerce")
                                .fillna(0)
                                .sum()
                            )
                            - month_invested
                        )
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
        return pd.DataFrame(columns=["month", "total_value", "total_invested", "month_label"])

    df_series = pd.DataFrame(months_data)
    if not df_series.empty:
        df_series["total_invested"] = df_series["month_invested"].cumsum().round(2)
        df_series = df_series.drop(columns=["month_invested"])
        df_series["month"] = pd.to_datetime(df_series["month"])

    now = pd.Timestamp.now().to_period("M").to_timestamp()
    if current_total_value is not None or current_total_invested is not None:
        if df_series.empty or df_series["month"].max().to_period("M") != now.to_period("M"):
            row: dict = {"month": now}
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
