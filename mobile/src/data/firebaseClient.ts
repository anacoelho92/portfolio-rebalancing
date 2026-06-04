/**
 * Mobile data layer: Firebase Auth + Firestore (no REST API for portfolio data).
 */
import { portfolioUsername, signIn, signOut } from "../auth/session";
import { getFirebaseAuth } from "../lib/firebase";
import type {
  AddStockPurchaseInput,
  AllocationResult,
  ChartData,
  DividendSummary,
  Holding,
  PortfolioDetail,
  StockPurchasesPayload,
} from "../types";
import { PORTFOLIO_TYPE_GROWTH } from "../portfolio/core";
import {
  calculateGrowthAllocation,
  calculateKidsAllocation,
  loadMaster,
  logGrowthInvestment,
  persistPortfolio,
} from "../portfolio/actions";
import { buildCharts } from "../portfolio/charts";
import { addDividendRecord, dividendSummary } from "../portfolio/dividends";
import { distinctUsernames, emptyDataMessage } from "../portfolio/diagnostics";
import { buildHomePayload, buildPortfolioSummary, portfolioNames } from "../portfolio/services";
import {
  addStockPurchase as addStockPurchaseOp,
  deleteStockUnit as deleteStockUnitOp,
  fetchStockPurchasesPayload,
  updateStockMarketValues as updateMarketValuesOp,
} from "../portfolio/stockPurchases";
import { readWorksheetRows } from "../firestore/worksheets";

async function requireUser() {
  const auth = getFirebaseAuth();
  await auth.authStateReady();
  const user = auth.currentUser;
  if (!user) throw new Error("Not signed in");
  return { user, username: portfolioUsername(user) };
}

export async function login(email: string, password: string) {
  return signIn(email, password);
}

export { signOut as logout };

export async function getToken(): Promise<string | null> {
  const { user } = await requireUser().catch(() => ({ user: null }));
  return user?.uid ?? null;
}

export async function fetchPortfolios() {
  const { username } = await requireUser();
  const master = await loadMaster();
  return buildHomePayload(master, username);
}

/** Explains empty portfolio list (missing migration, wrong username, etc.). */
export async function portfolioLoadHint(): Promise<string | null> {
  const { username } = await requireUser();
  const master = await loadMaster();
  if (portfolioNames(master, username).length > 0) return null;
  return emptyDataMessage(master.length, username, distinctUsernames(master));
}

export async function fetchPortfolio(name: string): Promise<PortfolioDetail> {
  const { username } = await requireUser();
  const master = await loadMaster();
  const purchases = await readWorksheetRows("StockPurchases");
  const dividends = await readWorksheetRows("Dividends");
  const log = await readWorksheetRows("InvestmentLog");
  return buildPortfolioSummary(master, username, name, purchases, dividends, log);
}

export async function savePortfolio(
  name: string,
  payload: {
    holdings: Holding[];
    monthly_invest?: number;
    uninvested_cash?: number;
    safe_liquidity?: number;
  }
) {
  const { username } = await requireUser();
  const master = await loadMaster();
  await persistPortfolio(master, username, name, payload.holdings, {
    monthly_invest: payload.monthly_invest,
    uninvested_cash: payload.uninvested_cash,
    safe_liquidity: payload.safe_liquidity,
  });
  return { status: "ok", message: "Portfolio saved" };
}

export async function calculateAllocation(
  name: string,
  opts?: { monthly_invest?: number; uninvested_cash?: number; safe_liquidity?: number }
): Promise<AllocationResult> {
  const { username } = await requireUser();
  const master = await loadMaster();
  const detail = await fetchPortfolio(name);
  if (detail.portfolio_type === PORTFOLIO_TYPE_GROWTH) {
    return calculateGrowthAllocation(master, username, name, opts);
  }
  if (detail.portfolio_type === "Kids") {
    return calculateKidsAllocation(master, username, name, opts);
  }
  throw new Error("Calculate allocation is only available for Growth and Kids portfolios.");
}

export async function logInvestment(
  name: string,
  opts?: { monthly_invest?: number; uninvested_cash?: number; safe_liquidity?: number }
) {
  const { username } = await requireUser();
  const master = await loadMaster();
  const detail = await fetchPortfolio(name);
  let calc: AllocationResult;
  if (detail.portfolio_type === PORTFOLIO_TYPE_GROWTH) {
    calc = calculateGrowthAllocation(master, username, name, opts);
    return logGrowthInvestment(master, username, name, calc);
  }
  throw new Error("Log investment is only implemented for Growth on mobile.");
}

export async function fetchCharts(name: string): Promise<ChartData> {
  const { username } = await requireUser();
  const master = await loadMaster();
  const purchases = await readWorksheetRows("StockPurchases");
  const dividends = await readWorksheetRows("Dividends");
  return buildCharts(master, username, name, purchases, dividends);
}

export async function fetchStockPurchases(name: string): Promise<StockPurchasesPayload> {
  const { username } = await requireUser();
  const master = await loadMaster();
  return fetchStockPurchasesPayload(master, username, name);
}

export async function addStockPurchase(
  name: string,
  body: AddStockPurchaseInput
) {
  const { username } = await requireUser();
  const master = await loadMaster();
  return addStockPurchaseOp(master, username, name, body);
}

export async function deleteStockUnit(name: string, unitKey: string) {
  const { username } = await requireUser();
  const master = await loadMaster();
  return deleteStockUnitOp(master, username, name, unitKey);
}

export async function deleteStockUnits(name: string, unitKeys: string[]) {
  const { username } = await requireUser();
  const master = await loadMaster();
  let payload = await fetchStockPurchasesPayload(master, username, name);
  for (const key of unitKeys) {
    payload = await deleteStockUnitOp(master, username, name, key);
  }
  return payload;
}

export async function updateStockMarketValues(
  name: string,
  marketValues: Record<string, number>
) {
  const { username } = await requireUser();
  const master = await loadMaster();
  return updateMarketValuesOp(master, username, name, marketValues);
}

export async function fetchDividends(name: string): Promise<DividendSummary> {
  const { username } = await requireUser();
  return dividendSummary(username, name);
}

export async function addDividend(
  name: string,
  body: { date: string; ticker: string; amount: number }
) {
  const { username } = await requireUser();
  return addDividendRecord(username, name, body);
}
