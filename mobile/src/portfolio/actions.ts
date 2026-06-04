import type { AllocationResult, Holding, RecommendationRow } from "../types";
import { readWorksheetRows, writeWorksheetRows } from "../firestore/worksheets";
import {
  allocateContribution,
  calculateInvestorAge,
  contributionWithUninvested,
  DEFAULT_INVESTOR_BIRTH_DATE,
  EXCLUDED_GD_TICKERS,
  filterByPortfolio,
  filterForUser,
  growthMonthlyBase,
  kidsMonthlyBase,
  PORTFOLIO_TYPE_GROWTH,
  SAFE_LIQUIDITY_LABEL,
  type MasterRow,
} from "./core";
import {
  growthStocksFromRows,
  kidsApplyTargets,
  portfolioMetadata,
  stocksFromRows,
} from "./data";
import { allocateStandardPortfolio } from "./allocationStandard";

export async function loadMaster(): Promise<MasterRow[]> {
  return readWorksheetRows("Portfolios");
}

export async function saveMaster(rows: MasterRow[]) {
  await writeWorksheetRows("Portfolios", rows);
}

export function calculateGrowthAllocation(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  opts?: { monthly_invest?: number; uninvested_cash?: number; safe_liquidity?: number }
): AllocationResult {
  const pRows = filterByPortfolio(filterForUser(master, username), portfolioName);
  const meta = portfolioMetadata(pRows);
  const stocks = growthStocksFromRows(pRows, meta.investor_birth_date);
  const month = new Date().getMonth() + 1;
  const investSetting = opts?.monthly_invest ?? meta.monthly_invest;
  const uninvested = opts?.uninvested_cash ?? meta.uninvested_cash;
  const safeBefore = opts?.safe_liquidity ?? meta.safe_liquidity;
  const base = growthMonthlyBase(investSetting, month);
  const contribution = contributionWithUninvested(base, uninvested);
  const currentValues = Object.fromEntries(stocks.map((s) => [s.name, s.current_value]));
  const age = calculateInvestorAge(meta.investor_birth_date);
  const plan = allocateContribution(contribution, age, currentValues);
  const portfolioValueAfter = plan.portfolio_value_after;
  const recommendations: RecommendationRow[] = [];

  for (const stock of stocks) {
    const ticker = stock.name;
    const inv = plan.buys[ticker] ?? 0;
    const targetPct = plan.portfolio_targets[ticker] ?? 0;
    const newVal = stock.current_value + inv;
    recommendations.push({
      stock: ticker,
      current_value: Math.round(stock.current_value * 100) / 100,
      current_pct: plan.current_weights[ticker] ?? 0,
      target_pct: targetPct,
      target_value: Math.round(((portfolioValueAfter * targetPct) / 100) * 100) / 100,
      investment: Math.round(inv * 100) / 100,
      new_value: Math.round(newVal * 100) / 100,
      new_pct:
        portfolioValueAfter > 0
          ? Math.round((newVal / portfolioValueAfter) * 10000) / 100
          : 0,
    });
  }

  const safeAfter = safeBefore + plan.cash_part;
  if (plan.cash_part > 0 || safeBefore > 0) {
    recommendations.push({
      stock: SAFE_LIQUIDITY_LABEL,
      current_value: Math.round(safeBefore * 100) / 100,
      current_pct:
        portfolioValueAfter > 0
          ? Math.round((safeBefore / portfolioValueAfter) * 10000) / 100
          : 0,
      target_pct: 0,
      target_value: 0,
      investment: Math.round(plan.cash_part * 100) / 100,
      new_value: Math.round(safeAfter * 100) / 100,
      new_pct:
        portfolioValueAfter > 0
          ? Math.round((safeAfter / portfolioValueAfter) * 10000) / 100
          : 0,
    });
  }

  const pieBefore = stocks
    .filter((s) => s.current_value > 0)
    .map((s) => ({ name: s.name, value: s.current_value }));
  const pieAfter = recommendations
    .filter((r) => !EXCLUDED_GD_TICKERS.has(r.stock.toUpperCase()) && r.new_value > 0)
    .map((r) => ({ name: r.stock, value: r.new_value }));

  return {
    recommendations,
    monthly_contribution: contribution,
    total_etf_investment: Object.values(plan.buys).reduce((a, b) => a + b, 0),
    safe_liquidity_after: Math.round(safeAfter * 100) / 100,
    portfolio_value_after: portfolioValueAfter,
    pie_before: pieBefore,
    pie_after: pieAfter,
    investor_age: age,
  };
}

export function calculateKidsAllocation(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  opts?: { uninvested_cash?: number }
): AllocationResult {
  const pRows = filterByPortfolio(filterForUser(master, username), portfolioName);
  const meta = portfolioMetadata(pRows);
  let stocks: import("./data").StockRow[] = stocksFromRows(pRows);
  if (meta.portfolio_birth_date) stocks = kidsApplyTargets(stocks, meta.portfolio_birth_date);
  const live = stocks
    .filter((s) => s.name && s.name !== "__PLACEHOLDER__")
    .map((s) => ({
      name: s.name,
      current_value: s.current_value,
      target_allocation: s.target_allocation,
      tolerance: s.tolerance,
      expense_ratio: s.expense_ratio,
    }));
  const uninvested = opts?.uninvested_cash ?? meta.uninvested_cash;
  const base = kidsMonthlyBase();
  const contribution = contributionWithUninvested(base, uninvested);
  const { investments } = allocateStandardPortfolio(live, contribution);
  const totalCurrent = live.reduce((s, x) => s + x.current_value, 0);
  const after = totalCurrent + contribution;
  const recommendations: RecommendationRow[] = live.map((stock) => {
    const inv = investments[stock.name] ?? 0;
    const newVal = stock.current_value + inv;
    return {
      stock: stock.name,
      current_value: Math.round(stock.current_value * 100) / 100,
      current_pct:
        totalCurrent > 0
          ? Math.round((stock.current_value / totalCurrent) * 10000) / 100
          : 0,
      target_pct: Math.round(stock.target_allocation * 100) / 100,
      target_value: Math.round(((after * stock.target_allocation) / 100) * 100) / 100,
      investment: Math.round(inv * 100) / 100,
      new_value: Math.round(newVal * 100) / 100,
      new_pct: after > 0 ? Math.round((newVal / after) * 10000) / 100 : 0,
    };
  });
  return {
    recommendations,
    monthly_contribution: contribution,
    total_etf_investment: Object.values(investments).reduce((a, b) => a + b, 0),
    safe_liquidity_after: meta.safe_liquidity,
    portfolio_value_after: Math.round(after * 100) / 100,
    pie_before: live.filter((s) => s.current_value > 0).map((s) => ({ name: s.name, value: s.current_value })),
    pie_after: recommendations.filter((r) => r.new_value > 0).map((r) => ({ name: r.stock, value: r.new_value })),
    investor_age: 0,
  };
}

export async function persistPortfolio(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  holdings: Holding[],
  opts?: { monthly_invest?: number; uninvested_cash?: number; safe_liquidity?: number }
) {
  const pRows = filterByPortfolio(filterForUser(master, username), portfolioName);
  const meta = portfolioMetadata(pRows);
  const pType = meta.portfolio_type;
  const rest = master.filter(
    (r) => !(String(r.username) === username && String(r.portfolio_name) === portfolioName)
  );
  const portfolioInvest = opts?.monthly_invest ?? meta.monthly_invest;
  const portfolioUninv = opts?.uninvested_cash ?? meta.uninvested_cash;
  const portfolioSafe = opts?.safe_liquidity ?? meta.safe_liquidity;
  const first = pRows[0];
  const portfolioUseInd = first?.portfolio_use_indicators ?? false;
  const portfolioBuffett = first?.portfolio_buffett_index ?? 195;
  const portfolioBirth = first?.portfolio_birth_date ?? "";
  const portfolioReinv = first?.portfolio_uninvested_reinvested ?? 0;

  const newRows: MasterRow[] = holdings
    .filter((h) => h.ticker && h.ticker !== "__PLACEHOLDER__")
    .map((h) => ({
      username,
      portfolio_name: portfolioName,
      stock_name: h.ticker,
      current_value: h.current_value,
      target_allocation: h.target_allocation,
      current_price: 0,
      tolerance: h.tolerance,
      expense_ratio: h.expense_ratio,
      portfolio_monthly_invest: portfolioInvest,
      portfolio_use_indicators: portfolioUseInd,
      portfolio_buffett_index: portfolioBuffett,
      portfolio_birth_date: portfolioBirth,
      portfolio_uninvested_cash: portfolioUninv,
      portfolio_safe_liquidity: portfolioSafe,
      portfolio_uninvested_reinvested: portfolioReinv,
      investor_birth_date: first?.investor_birth_date ?? DEFAULT_INVESTOR_BIRTH_DATE,
      portfolio_type: pType,
      stock_full_name: h.ticker,
      sector: "",
      industry: "",
      country: "",
      currency: "",
      quantity: 0,
      average_price: 0,
      dividend_yield: 0,
    }));

  if (!newRows.length) {
    newRows.push({
      username,
      portfolio_name: portfolioName,
      stock_name: "__PLACEHOLDER__",
      portfolio_type: pType,
      portfolio_monthly_invest: portfolioInvest,
      portfolio_uninvested_cash: portfolioUninv,
      portfolio_safe_liquidity: portfolioSafe,
      investor_birth_date: DEFAULT_INVESTOR_BIRTH_DATE,
    });
  }

  await saveMaster([...rest, ...newRows]);
}

export async function logGrowthInvestment(
  master: MasterRow[],
  username: string,
  portfolioName: string,
  calc: AllocationResult
) {
  const log = await readWorksheetRows("InvestmentLog");
  const ts = new Date().toISOString().slice(0, 19).replace("T", " ");
  const newEntries = calc.recommendations
    .filter((r) => !EXCLUDED_GD_TICKERS.has(r.stock.toUpperCase()))
    .map((r) => ({
      timestamp: ts,
      username,
      portfolio_name: portfolioName,
      Stock: r.stock,
      "Current Value": r.current_value,
      "Current %": r.current_pct,
      "Target %": r.target_pct,
      "Target Value": r.target_value,
      Investment: r.investment,
      "New Value": r.new_value,
      "New %": r.new_pct,
    }));
  await writeWorksheetRows("InvestmentLog", [...log, ...newEntries]);

  let updated = [...master];
  for (const row of calc.recommendations) {
    if (row.stock === SAFE_LIQUIDITY_LABEL) continue;
    updated = updated.map((r) =>
      String(r.username) === username &&
      String(r.portfolio_name) === portfolioName &&
      String(r.stock_name) === row.stock
        ? { ...r, current_value: row.new_value }
        : r
    );
  }
  const safeAfter = calc.safe_liquidity_after;
  updated = updated.map((r) =>
    String(r.username) === username && String(r.portfolio_name) === portfolioName
      ? { ...r, portfolio_safe_liquidity: safeAfter }
      : r
  );
  await saveMaster(updated);
  return { status: "ok", message: "Logged and portfolio updated" };
}
