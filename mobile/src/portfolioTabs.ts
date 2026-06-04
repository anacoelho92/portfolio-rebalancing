export type PortfolioTabId = "manage" | "details" | "dividends" | "cash";

export type PortfolioTab = { id: PortfolioTabId; label: string };

export function portfolioTabs(
  portfolioType: string,
  portfolioName: string
): PortfolioTab[] {
  const isConviction = portfolioName.toLowerCase().includes("conviction");

  if (portfolioType === "Overview") {
    return [];
  }
  if (portfolioType === "Stocks") {
    const tabs: PortfolioTab[] = [
      { id: "details", label: "📈 Details" },
      { id: "dividends", label: "💰 Dividends" },
      { id: "cash", label: "🪙 Cash" },
    ];
    if (isConviction) {
      return tabs.filter((t) => t.id !== "cash");
    }
    return tabs;
  }
  const tabs: PortfolioTab[] = [
    { id: "manage", label: "📊 Manage Portfolio" },
    { id: "cash", label: "🪙 Uninvested Cash" },
  ];
  if (isConviction) {
    return tabs.filter((t) => t.id !== "cash");
  }
  return tabs;
}

export function defaultTab(portfolioType: string): PortfolioTabId {
  if (portfolioType === "Stocks") return "details";
  return "manage";
}
