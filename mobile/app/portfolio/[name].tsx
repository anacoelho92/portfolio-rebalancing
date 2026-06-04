import { useFocusEffect, useLocalSearchParams } from "expo-router";
import { useCallback, useRef, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  AllocationResult,
  calculateAllocation,
  ChartData,
  fetchCharts,
  fetchPortfolio,
  Holding,
  logInvestment,
  PortfolioDetail,
  savePortfolio,
} from "../../src/api";
import { DividendTrackerPanel } from "../../src/components/DividendTrackerPanel";
import { GlobalOverviewSection } from "../../src/components/GlobalOverviewSection";
import { GrowthAllocationPanel } from "../../src/components/GrowthAllocationPanel";
import { PortfolioManagementTable } from "../../src/components/PortfolioManagementTable";
import { PortfolioKpiSection } from "../../src/components/PortfolioKpiSection";
import { StocksPortfolioSection } from "../../src/components/StocksPortfolioSection";
import { UninvestedCashPanel } from "../../src/components/UninvestedCashPanel";
import { Card } from "../../src/components/ui/Card";
import { InfoBanner } from "../../src/components/ui/InfoBanner";
import { SectionHeader } from "../../src/components/ui/SectionHeader";
import { StreamlitTabBar } from "../../src/components/ui/StreamlitTabBar";
import {
  defaultTab,
  portfolioTabs,
  type PortfolioTabId,
} from "../../src/portfolioTabs";
import { colors, spacing } from "../../src/theme";

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function PortfolioDetailScreen() {
  const { name } = useLocalSearchParams<{ name: string }>();
  const portfolioName = decodeURIComponent(name || "");
  const [tab, setTab] = useState<PortfolioTabId>("manage");
  const [detail, setDetail] = useState<PortfolioDetail | null>(null);
  const [editable, setEditable] = useState<Holding[]>([]);
  const [monthlyInvest, setMonthlyInvest] = useState("");
  const [uninvestedCash, setUninvestedCash] = useState("");
  const [safeLiquidity, setSafeLiquidity] = useState("");
  const [allocation, setAllocation] = useState<AllocationResult | null>(null);
  const [charts, setCharts] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const kidsSaveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isGrowth = detail?.portfolio_type === "Growth";
  const isKids = detail?.portfolio_type === "Kids";
  const isStocks = detail?.portfolio_type === "Stocks";
  const isOverview = detail?.portfolio_type === "Overview";

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await fetchPortfolio(portfolioName);
      setDetail(data);
      setTab(defaultTab(data.portfolio_type));
      setEditable(data.holdings.map((h) => ({ ...h })));
      setMonthlyInvest(String(data.monthly_invest ?? ""));
      setUninvestedCash(String(data.uninvested_cash ?? ""));
      setSafeLiquidity(String(data.safe_liquidity ?? ""));
      if (data.portfolio_type !== "Overview") {
        const chartData = await fetchCharts(portfolioName);
        setCharts(chartData);
      } else {
        setCharts(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [portfolioName]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  const configOpts = () => ({
    monthly_invest: monthlyInvest ? parseFloat(monthlyInvest) : undefined,
    uninvested_cash: uninvestedCash ? parseFloat(uninvestedCash) : undefined,
    safe_liquidity: safeLiquidity ? parseFloat(safeLiquidity) : undefined,
  });

  async function persistPortfolio() {
    await savePortfolio(portfolioName, {
      holdings: editable,
      ...configOpts(),
    });
    await load();
  }

  function queueKidsSave() {
    if (!isKids) return;
    if (kidsSaveTimer.current) clearTimeout(kidsSaveTimer.current);
    kidsSaveTimer.current = setTimeout(() => {
      kidsSaveTimer.current = null;
      setBusy(true);
      setError(null);
      persistPortfolio()
        .then(() => setSuccess("Portfolio saved"))
        .catch((e) =>
          setError(e instanceof Error ? e.message : "Save failed")
        )
        .finally(() => setBusy(false));
    }, 800);
  }

  async function onCalculate() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      await persistPortfolio();
      const result = await calculateAllocation(portfolioName, configOpts());
      setAllocation(result);
      setSuccess("Saved & allocation calculated");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  }

  async function onLog() {
    Alert.alert(
      "Log investment",
      "This writes to InvestmentLog and updates portfolio values in Firestore, like Streamlit.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Log",
          onPress: async () => {
            setBusy(true);
            setError(null);
            try {
              await persistPortfolio();
              await logInvestment(portfolioName, configOpts());
              setSuccess("Saved, logged & portfolio updated");
              setAllocation(null);
              await load();
            } catch (e) {
              setError(e instanceof Error ? e.message : "Log failed");
            } finally {
              setBusy(false);
            }
          },
        },
      ]
    );
  }

  function updateHolding(ticker: string, field: keyof Holding, value: string) {
    setEditable((prev) =>
      prev.map((h) =>
        h.ticker === ticker
          ? { ...h, [field]: field === "ticker" ? value : parseFloat(value) || 0 }
          : h
      )
    );
    queueKidsSave();
  }

  if (loading && !detail) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    );
  }

  if (!detail || isOverview) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <GlobalOverviewSection detail={detail} loading={loading && !detail} />
      </ScrollView>
    );
  }

  const tabs = portfolioTabs(detail.portfolio_type, portfolioName);
  const uninvestedNum = parseFloat(uninvestedCash) || 0;
  const targetSum = detail.target_sum ?? 0;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{detail.name}</Text>

      <PortfolioKpiSection detail={detail} />

      {uninvestedNum > 0 && tab !== "cash" ? (
        <InfoBanner
          message={`💡 You have ${formatEuro(uninvestedNum)} of uninvested cash. Manage it in the Uninvested Cash tab.`}
        />
      ) : null}
      {!isStocks && Math.abs(targetSum - 100) > 0.01 ? (
        <InfoBanner
          variant="warning"
          message="⚠️ Target allocations do not sum to 100%. Adjust them in Manage Portfolio."
        />
      ) : null}

      <StreamlitTabBar tabs={tabs} active={tab} onChange={setTab} />

      {error ? <Text style={styles.error}>{error}</Text> : null}
      {success ? <Text style={styles.success}>{success}</Text> : null}

      {tab === "details" && isStocks ? (
        <StocksPortfolioSection
          portfolioName={portfolioName}
          charts={charts}
          onPortfolioUpdated={load}
        />
      ) : null}

      {tab === "dividends" && isStocks ? (
        <DividendTrackerPanel portfolioName={portfolioName} holdings={editable} />
      ) : null}

      {tab === "cash" ? (
        <UninvestedCashPanel
          portfolioName={portfolioName}
          uninvestedCash={uninvestedNum}
          holdings={editable}
          onSaved={load}
        />
      ) : null}

      {tab === "manage" && !isStocks ? (
        <>
          <Card>
            <SectionHeader title="📝 Portfolio Management" />
            <PortfolioManagementTable
              holdings={editable}
              portfolioType={detail.portfolio_type}
              busy={busy}
              monthlyInvest={monthlyInvest}
              safeLiquidity={safeLiquidity}
              onMonthlyInvestChange={isGrowth ? setMonthlyInvest : undefined}
              onSafeLiquidityChange={isGrowth ? setSafeLiquidity : undefined}
              onUpdate={updateHolding}
            />
          </Card>
          {isGrowth || isKids ? (
            <GrowthAllocationPanel
              portfolioType={detail.portfolio_type}
              allocation={allocation}
              charts={charts}
              busy={busy}
              onCalculate={onCalculate}
              onLog={isGrowth ? onLog : undefined}
            />
          ) : null}
        </>
      ) : null}

      {busy ? <ActivityIndicator color={colors.accent} style={{ marginTop: spacing.md }} /> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 3 },
  centered: {
    flex: 1,
    backgroundColor: colors.bg,
    justifyContent: "center",
    alignItems: "center",
  },
  title: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "800",
    marginBottom: spacing.sm,
  },
  kpiRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.md },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  rowTitle: { color: colors.text },
  rowValue: { color: colors.text, fontWeight: "600" },
  error: { color: colors.danger, marginBottom: spacing.sm },
  success: { color: colors.accent, marginBottom: spacing.sm },
});
