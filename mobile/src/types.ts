export type PortfolioListItem = {
  name: string;
  portfolio_type: string;
  total_value: number;
};

export type Holding = {
  ticker: string;
  current_value: number;
  target_allocation: number;
  tolerance: number;
  expense_ratio: number;
  total_invested?: number;
  quantity?: number;
  sector?: string;
  industry?: string;
  country?: string;
  dividend_yield?: number;
};

export type PortfolioDetail = {
  name: string;
  portfolio_type: string;
  total_value: number;
  target_sum?: number;
  weighted_ter?: number;
  holdings_count?: number;
  total_invested?: number;
  profit?: number;
  profit_pct?: number;
  volumes_count?: number;
  num_sectors?: number;
  portfolio_div_yield?: number;
  portfolio_yoc?: number;
  monthly_invest?: number;
  uninvested_cash?: number;
  safe_liquidity?: number;
  holdings: Holding[];
  breakdown?: { name: string; total_value: number; portfolio_type: string }[];
};

export type RecommendationRow = {
  stock: string;
  current_value: number;
  current_pct: number;
  target_pct: number;
  target_value: number;
  investment: number;
  new_value: number;
  new_pct: number;
};

export type AllocationResult = {
  recommendations: RecommendationRow[];
  monthly_contribution: number;
  total_etf_investment: number;
  safe_liquidity_after: number;
  portfolio_value_after: number;
  pie_before: { name: string; value: number }[];
  pie_after: { name: string; value: number }[];
  investor_age: number;
  withdrawal?: Record<string, unknown>;
};

export type PieSlice = { name: string; value: number };

export type ChartData = {
  time_series: { month: string; total_value: number; total_invested: number | null }[];
  holdings_pie: PieSlice[];
  total_value: number;
  total_invested: number;
  distributions?: {
    by_stock?: PieSlice[];
    by_sector?: PieSlice[];
    by_industry?: PieSlice[];
    by_country?: PieSlice[];
    by_portfolio?: PieSlice[];
  };
};

export type StockPurchaseUnit = {
  unit_key: string;
  purchase_id: string;
  unit_index: number;
  ticker: string;
  price: number;
  currency: string;
  dividend_yield: number;
  fractional: boolean;
  display_qty?: number;
};

export type StockSummary = {
  ticker: string;
  name: string;
  quantity: number;
  invested_value: number;
  avg_price: number;
  market_value: number;
  div_yield: number;
  current_pct?: number;
  target_allocation?: number;
  tolerance?: number;
  yoc?: number;
  received_yoc?: number;
  above_avg_15?: number;
  below_lowest_10?: number;
  sector: string;
  industry: string;
  country?: string;
  currency?: string;
};

export type StockPurchasesPayload = {
  purchases: unknown[];
  units: StockPurchaseUnit[];
  units_by_ticker: Record<string, StockPurchaseUnit[]>;
  summaries: StockSummary[];
  total_market_value: number;
  total_invested: number;
};

export type AddStockPurchaseInput = {
  ticker: string;
  unit_price: number;
  quantity: number;
  sector?: string;
  industry?: string;
  country?: string;
  currency?: string;
  dividend_yield?: number;
};

export type DividendRecord = {
  date: string;
  ticker: string;
  amount: number;
};

export type DividendYearSeries = {
  year: string;
  amounts: number[];
};

export type DividendMonthlyComparison = {
  months: string[];
  series: DividendYearSeries[];
};

export type DividendSummary = {
  records: DividendRecord[];
  total_current_year: number;
  total_previous_year: number;
  current_year: number;
  monthly_comparison: DividendMonthlyComparison;
  tickers: string[];
};
