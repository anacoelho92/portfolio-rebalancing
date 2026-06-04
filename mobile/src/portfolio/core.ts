/** Port of portfolio_core.py (Growth + Kids + filters). */

export const RETIREMENT_AGE = 67;
export const WITHDRAWAL_RATE = 0.035;
export const BASE_CONTRIBUTION = 500;
export const PORTFOLIO_TYPE_GROWTH = "Growth";
export const SAFE_LIQUIDITY_LABEL = "Safe Liquidity";
export const GLOBAL_OVERVIEW_LABEL = "🌍 Global Overview";
export const DEFAULT_INVESTOR_BIRTH_DATE = "1992-01-01";
export const EXCLUDED_GD_TICKERS = new Set([
  "YCSH.DE",
  "PRAB.DE",
  "IBTE.UK",
  "WTEQ.DE",
  "VDIV.DE",
  "JMT.PT",
  "EDP.PT",
]);

export const GD_TICKER_MAP: Record<string, string> = {
  SPYL: "SPYL.DE",
  IXUA: "IXUA.DE",
  VFEA: "VFEA.DE",
  GOLD: "EGLN.UK",
};

export const GROWTH_DIVIDENDS_TICKERS = ["SPYL.DE", "IXUA.DE", "VFEA.DE", "EGLN.UK"];

export const TOLERANCE_PP: Record<string, number> = {
  "SPYL.DE": 5,
  "IXUA.DE": 5,
  "VFEA.DE": 3,
  "EGLN.UK": 2,
};

export const KIDS_ETF_VWCE = "VWCE.DE";
export const KIDS_ETF_VAGF = "VAGF.DE";

export type MasterRow = Record<string, unknown>;

export function safeFloat(v: unknown, fallback = 0): number {
  if (v == null || v === "") return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function normalizePortfolioType(p: string): string {
  const t = String(p).trim();
  if (t === "Unified" || t === "Growth & Dividends") return PORTFOLIO_TYPE_GROWTH;
  return t;
}

export function filterForUser(rows: MasterRow[], username: string): MasterRow[] {
  const u = username.trim();
  return rows.filter((r) => String(r.username ?? "").trim() === u);
}

export function filterByPortfolio(rows: MasterRow[], portfolioName: string): MasterRow[] {
  return rows.filter((r) => String(r.portfolio_name ?? "") === portfolioName);
}

export function goldTarget(age: number): number {
  if (age <= 55) return 3;
  if (age >= RETIREMENT_AGE) return 10;
  return 3 + ((age - 55) / 12) * 7;
}

export function targetWeights(age: number): Record<string, number> {
  const gold = goldTarget(age);
  const growth = 100 - gold;
  const base = 55 + 30 + 12;
  return {
    SPYL: (growth * 55) / base,
    IXUA: (growth * 30) / base,
    VFEA: (growth * 12) / base,
    GOLD: gold,
  };
}

export function growthTargetsByTicker(age: number): Record<string, number> {
  const raw = targetWeights(age);
  return Object.fromEntries(
    Object.entries(raw).map(([k, v]) => [GD_TICKER_MAP[k] ?? k, v])
  );
}

export function cashSplit(age: number): number {
  if (age < 60) return 0;
  if (age < 62) return 0.2;
  if (age < 64) return 0.4;
  if (age < 66) return 0.6;
  if (age < RETIREMENT_AGE) return 0.8;
  return 1;
}

export function roundWeights(w: Record<string, number>, d = 2): Record<string, number> {
  return Object.fromEntries(Object.entries(w).map(([k, v]) => [k, Math.round(v * 10 ** d) / 10 ** d]));
}

export function calculateInvestorAge(birth: string): number {
  try {
    const b = new Date(birth);
    const t = new Date();
    let age = t.getFullYear() - b.getFullYear();
    const m = t.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && t.getDate() < b.getDate())) age--;
    return age;
  } catch {
    return 34;
  }
}

export function getTolerance(ticker: string): number {
  let t = ticker.toUpperCase();
  if (t === "EGNL.UK") t = "EGLN.UK";
  return TOLERANCE_PP[t] ?? 2;
}

export function buildToleranceMap(targets: Record<string, number>): Record<string, number> {
  return Object.fromEntries(Object.keys(targets).map((t) => [t, getTolerance(t)]));
}

export function growthMonthlyBase(monthlyInvest: number, month: number): number {
  const base = Math.max(0, monthlyInvest);
  return month === 6 || month === 12 ? Math.round(base * 2 * 100) / 100 : Math.round(base * 100) / 100;
}

export function contributionWithUninvested(base: number, uninvested: number): number {
  return Math.round((base + Math.max(0, uninvested)) * 100) / 100;
}

function sellProportionally(current: Record<string, number>, amount: number): Record<string, number> {
  const total = Object.values(current).reduce((a, b) => a + b, 0);
  if (amount <= 0 || total <= 0) return {};
  return Object.fromEntries(
    Object.keys(current).map((k) => [k, (current[k]! / total) * amount])
  );
}

export function applyCentsToLargest(
  investments: Record<string, number>,
  budget: number
): Record<string, number> {
  const result: Record<string, number> = {};
  let floored = 0;
  for (const [t, amount] of Object.entries(investments)) {
    if (amount > 0) {
      const f = Math.floor(amount);
      result[t] = f;
      floored += f;
    } else {
      result[t] = 0;
    }
  }
  const remainder = Math.round((budget - floored) * 100) / 100;
  const positive = Object.entries(result).filter(([, v]) => v > 0);
  if (remainder > 0 && positive.length) {
    const dump = positive.reduce((a, b) => (b[1] > a[1] ? b : a))[0];
    result[dump] = Math.round((result[dump]! + remainder) * 100) / 100;
  }
  return result;
}

function distributeLeftover(buys: Record<string, number>, leftover: number): Record<string, number> {
  if (leftover <= 0) return buys;
  const result = { ...buys };
  const additions = sellProportionally(result, leftover);
  for (const [t, a] of Object.entries(additions)) {
    result[t] = Math.round((result[t]! + a) * 100) / 100;
  }
  return result;
}

export function allocateContribution(
  contribution: number,
  age: number,
  currentValues: Record<string, number>,
  minOrder = 5
) {
  const targets = growthTargetsByTicker(age);
  const assets = Object.keys(targets);
  const cashFraction = cashSplit(age);
  const cashPart = Math.round(contribution * cashFraction * 100) / 100;
  const investPart = Math.round((contribution - cashPart) * 100) / 100;
  const portfolioValue = assets.reduce((s, a) => s + (currentValues[a] ?? 0), 0);
  const newTotal = portfolioValue + contribution;
  const tolerances = buildToleranceMap(targets);
  const currentWeights: Record<string, number> = {};
  for (const a of assets) {
    currentWeights[a] =
      portfolioValue <= 0 ? 0 : ((currentValues[a] ?? 0) / portfolioValue) * 100;
  }
  const deficits = Object.fromEntries(
    assets.map((a) => [a, targets[a]! - currentWeights[a]!])
  );
  const rawBuys: Record<string, number> = Object.fromEntries(assets.map((a) => [a, 0]));
  let remaining = investPart;
  const belowMinBand: string[] = [];

  if (investPart > 0) {
    const bandNeeds: Record<string, number> = {};
    for (const a of assets) {
      const minBand = targets[a]! - tolerances[a]!;
      if (currentWeights[a]! < minBand) {
        belowMinBand.push(a);
        const minVal = (newTotal * minBand) / 100;
        bandNeeds[a] = Math.max(0, minVal - (currentValues[a] ?? 0));
      }
    }
    const totalBand = Object.values(bandNeeds).reduce((s, v) => s + v, 0);
    if (totalBand > 0 && remaining > 0) {
      if (totalBand <= remaining) {
        for (const [a, need] of Object.entries(bandNeeds)) {
          rawBuys[a] = (rawBuys[a] ?? 0) + need;
          remaining -= need;
        }
      } else {
        for (const [a, need] of Object.entries(bandNeeds)) {
          rawBuys[a] = (rawBuys[a] ?? 0) + (need / totalBand) * remaining;
        }
        remaining = 0;
      }
    }
    if (remaining > 0) {
      const gaps: Record<string, number> = {};
      let totalGap = 0;
      for (const a of assets) {
        if (deficits[a]! > 0) {
          const g = Math.max(
            0,
            (newTotal * targets[a]!) / 100 - (currentValues[a] ?? 0) - (rawBuys[a] ?? 0)
          );
          gaps[a] = g;
          totalGap += g;
        }
      }
      if (totalGap > 0) {
        for (const [a, g] of Object.entries(gaps)) {
          rawBuys[a] = (rawBuys[a] ?? 0) + (remaining * g) / totalGap;
        }
      } else {
        const sum = Object.values(targets).reduce((s, v) => s + v, 0);
        for (const a of assets) {
          rawBuys[a] = (rawBuys[a] ?? 0) + (remaining * targets[a]!) / sum;
        }
      }
    }
  }

  for (const a of assets) {
    if ((rawBuys[a] ?? 0) < minOrder) rawBuys[a] = 0;
  }
  let buys = applyCentsToLargest(rawBuys, investPart);
  let invested = Object.values(buys).reduce((s, v) => s + v, 0);
  let leftover = Math.round(Math.max(0, investPart - invested) * 100) / 100;
  if (leftover > 0) {
    buys = distributeLeftover(buys, leftover);
    invested = Object.values(buys).reduce((s, v) => s + v, 0);
    leftover = Math.round(Math.max(0, investPart - invested) * 100) / 100;
    if (leftover > 0) {
      const dump = Object.entries(buys)
        .filter(([, v]) => v > 0)
        .reduce((a, b) => (b[1] > a[1] ? b : a))?.[0];
      if (dump) {
        buys[dump] = Math.round((buys[dump]! + leftover) * 100) / 100;
        leftover = 0;
      }
    }
  }

  return {
    portfolio_value_before: Math.round(portfolioValue * 100) / 100,
    portfolio_value_after: Math.round(newTotal * 100) / 100,
    portfolio_targets: roundWeights(targets),
    current_weights: roundWeights(currentWeights),
    cash_part: cashPart,
    cash_split: cashFraction,
    buys,
    leftover_cash: leftover,
  };
}

export function kidsTargetsFromBirth(birth: string): Record<string, number> | null {
  const age = calculateInvestorAge(birth);
  let vwce = 100;
  let vagf = 0;
  if (age <= 12) {
    vwce = 100;
    vagf = 0;
  } else if (age >= 20) {
    vwce = 70;
    vagf = 30;
  } else {
    const p = (age - 12) / 8;
    vwce = 100 - 30 * p;
    vagf = 30 * p;
  }
  return { [KIDS_ETF_VWCE]: Math.round(vwce * 10) / 10, [KIDS_ETF_VAGF]: Math.round(vagf * 10) / 10 };
}

export function kidsMonthlyBase(): number {
  const now = new Date();
  let month = now.getMonth() + 1;
  if (now.getDate() >= 28) {
    month = month === 12 ? 1 : month + 1;
  }
  return month === 6 || month === 12 ? 100 : 50;
}
