import type { DividendSummary } from "../types";
import { readWorksheetRows, writeWorksheetRows } from "../firestore/worksheets";
import type { MasterRow } from "./core";
import { safeFloat } from "./core";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function filterDivs(rows: MasterRow[], username: string, portfolio: string) {
  return rows.filter(
    (r) =>
      String(r.username) === username &&
      String(r.portfolio_name) === portfolio &&
      r.date != null &&
      String(r.date).trim() !== ""
  );
}

function monthlyComparison(sub: MasterRow[], year: number) {
  const prev = year - 1;
  const amountsFor = (y: number) =>
    MONTHS.map((_, i) => {
      const m = i + 1;
      return Math.round(
        sub
          .filter((r) => {
            const d = new Date(String(r.date));
            return d.getFullYear() === y && d.getMonth() + 1 === m;
          })
          .reduce((s, r) => s + safeFloat(r.amount), 0) * 100
      ) / 100;
    });
  return {
    months: MONTHS,
    series: [
      { year: String(prev), amounts: amountsFor(prev) },
      { year: String(year), amounts: amountsFor(year) },
    ],
  };
}

export async function dividendSummary(
  username: string,
  portfolioName: string
): Promise<DividendSummary> {
  const all = await readWorksheetRows("Dividends");
  const sub = filterDivs(all, username, portfolioName);
  const year = new Date().getFullYear();
  const totalCurrent = sub
    .filter((r) => new Date(String(r.date)).getFullYear() === year)
    .reduce((s, r) => s + safeFloat(r.amount), 0);
  const totalPrev = sub
    .filter((r) => new Date(String(r.date)).getFullYear() === year - 1)
    .reduce((s, r) => s + safeFloat(r.amount), 0);
  const records = [...sub]
    .sort((a, b) => String(b.date).localeCompare(String(a.date)))
    .map((r) => ({
      date: String(r.date).slice(0, 10),
      ticker: String(r.ticker ?? ""),
      amount: Math.round(safeFloat(r.amount) * 100) / 100,
    }));
  const tickers = [...new Set(records.map((r) => r.ticker))].sort();
  return {
    records,
    total_current_year: Math.round(totalCurrent * 100) / 100,
    total_previous_year: Math.round(totalPrev * 100) / 100,
    current_year: year,
    monthly_comparison: monthlyComparison(sub, year),
    tickers,
  };
}

export async function addDividendRecord(
  username: string,
  portfolioName: string,
  body: { date: string; ticker: string; amount: number }
): Promise<DividendSummary> {
  const all = await readWorksheetRows("Dividends");
  const row = {
    date: `${body.date} 00:00:00`,
    ticker: body.ticker,
    amount: body.amount,
    portfolio_name: portfolioName,
    username,
  };
  await writeWorksheetRows("Dividends", [...all, row]);
  return dividendSummary(username, portfolioName);
}
