import type { PortfolioListItem } from "./api";

/** Same label as Streamlit / API (`portfolio_core.GLOBAL_OVERVIEW_LABEL`). */
export const GLOBAL_OVERVIEW_LABEL = "🌍 Global Overview";

export function isGlobalOverview(item: PortfolioListItem): boolean {
  return (
    item.portfolio_type === "Overview" ||
    item.name === GLOBAL_OVERVIEW_LABEL
  );
}

/** Portfolios shown in the home menu (excludes global overview). */
export function portfolioMenuItems(items: PortfolioListItem[]): PortfolioListItem[] {
  return items
    .filter((i) => !isGlobalOverview(i))
    .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
}

export function formatPortfolioNavLabel(item: PortfolioListItem): string {
  if (isGlobalOverview(item)) {
    return "🌍 Global Overview";
  }

  let name = item.name.replace("Growth & Dividends", "Growth");
  const lower = name.toLowerCase();
  if (lower.includes("grow") || lower.includes("accum")) {
    return `🌱 ${name}`;
  }
  if (lower.includes("dividend")) {
    return `💸 ${name}`;
  }

  switch (item.portfolio_type) {
    case "Stocks":
      return `📈 ${name}`;
    case "Kids":
      return `🧸 ${name}`;
    case "Growth":
      return `🏛️ ${name}`;
    default:
      return `📁 ${name}`;
  }
}
