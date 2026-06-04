import type { ChartData, PieSlice } from "../types";
import { readWorksheetRows } from "../firestore/worksheets";
import { GLOBAL_OVERVIEW_LABEL, PORTFOLIO_TYPE_GROWTH, type MasterRow } from "./core";
import { buildPortfolioSummary } from "./services";

export async function buildCharts(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  purchases: MasterRow[],
  dividends: MasterRow[]
): Promise<ChartData> {
  const summary = await buildPortfolioSummary(
    master,
    username,
    portfolioName,
    purchases,
    dividends,
    await readWorksheetRows("InvestmentLog")
  );

  if (portfolioName === GLOBAL_OVERVIEW_LABEL) {
    const pie: PieSlice[] = (summary.breakdown ?? []).map((b) => ({
      name: b.name,
      value: b.total_value,
    }));
    return {
      time_series: [],
      holdings_pie: pie,
      total_value: summary.total_value,
      total_invested: 0,
      distributions: { by_portfolio: pie },
    };
  }

  const log = await readWorksheetRows("InvestmentLog");
  const subset = log.filter(
    (r) =>
      String(r.username) === username && String(r.portfolio_name) === portfolioName
  );
  const months: { month: string; total_value: number; total_invested: number }[] = [];
  const byMonth: Record<string, MasterRow[]> = {};
  for (const r of subset) {
    const d = new Date(String(r.timestamp ?? r.Timestamp ?? ""));
    if (Number.isNaN(d.getTime())) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    if (!byMonth[key]) byMonth[key] = [];
    byMonth[key].push(r);
  }
  let cumInvested = 0;
  for (const key of Object.keys(byMonth).sort()) {
    const rows = byMonth[key]!;
    const monthInvest = rows.reduce(
      (s, r) => s + Number(r.Investment ?? r.investment ?? 0),
      0
    );
    cumInvested += monthInvest;
    const last = rows[rows.length - 1]!;
    const tv = rows.reduce(
      (s, r) => s + Number(r["New Value"] ?? r.new_value ?? 0),
      0
    );
    months.push({
      month: key,
      total_value: Math.round(tv * 100) / 100,
      total_invested: Math.round(cumInvested * 100) / 100,
    });
  }

  const holdingsPie: PieSlice[] = summary.holdings
    .filter((h) => h.current_value > 0)
    .map((h) => ({ name: h.ticker, value: h.current_value }));

  let chartValue = summary.total_value;
  if (summary.portfolio_type === PORTFOLIO_TYPE_GROWTH) {
    chartValue += summary.safe_liquidity ?? 0;
  }

  return {
    time_series: months.map((m) => ({
      month: m.month,
      total_value: m.total_value,
      total_invested: m.total_invested,
    })),
    holdings_pie: holdingsPie,
    total_value: chartValue,
    total_invested: summary.total_invested ?? 0,
    distributions:
      summary.portfolio_type === "Stocks"
        ? buildStockDistributions(summary.holdings)
        : undefined,
  };
}

function buildStockDistributions(
  holdings: { ticker: string; current_value: number; sector?: string; industry?: string; country?: string }[]
) {
  const byStock = holdings
    .filter((h) => h.current_value > 0)
    .map((h) => ({ name: h.ticker, value: h.current_value }));
  const sectorSums: Record<string, number> = {};
  const industrySums: Record<string, number> = {};
  const countrySums: Record<string, number> = {};
  for (const h of holdings) {
    const sec = (h as { sector?: string }).sector || "Unknown";
    const ind = (h as { industry?: string }).industry || "Unknown";
    const c = (h as { country?: string }).country || "Unknown";
    sectorSums[sec] = (sectorSums[sec] ?? 0) + h.current_value;
    industrySums[ind] = (industrySums[ind] ?? 0) + h.current_value;
    countrySums[c] = (countrySums[c] ?? 0) + h.current_value;
  }
  const toPie = (m: Record<string, number>) =>
    Object.entries(m).map(([name, value]) => ({ name, value: Math.round(value * 100) / 100 }));
  return {
    by_stock: byStock,
    by_sector: toPie(sectorSums),
    by_industry: toPie(industrySums),
    by_country: toPie(countrySums),
  };
}
