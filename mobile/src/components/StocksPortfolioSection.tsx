import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import {
  ChartData,
  fetchStockPurchases,
  StockPurchasesPayload,
  updateStockMarketValues,
} from "../api";
import { DonutPieChart } from "./DonutPieChart";
import { StocksPurchasesManage } from "./StocksPurchasesManage";
import { StocksSummaryTable } from "./StocksSummaryTable";
import { colors, spacing } from "../theme";

type Props = {
  portfolioName: string;
  charts: ChartData | null;
  onPortfolioUpdated: () => void;
};

type DistKey = "by_stock" | "by_sector" | "by_industry" | "by_country";

const DIST_TABS: { key: DistKey; title: string }[] = [
  { key: "by_stock", title: "By stock" },
  { key: "by_sector", title: "By sector" },
  { key: "by_industry", title: "By industry" },
  { key: "by_country", title: "By country" },
];

export function StocksPortfolioSection({
  portfolioName,
  charts,
  onPortfolioUpdated,
}: Props) {
  const [data, setData] = useState<StockPurchasesPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [distTab, setDistTab] = useState<DistKey>("by_stock");

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const payload = await fetchStockPurchases(portfolioName);
      setData(payload);
    } catch (e) {
      setData(null);
      setLoadError(
        e instanceof Error ? e.message : "Failed to load stock purchases"
      );
    } finally {
      setLoading(false);
    }
  }, [portfolioName]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const refreshAll = async () => {
    await load();
    onPortfolioUpdated();
  };

  const distributions = charts?.distributions;
  const distData = distributions?.[distTab] ?? [];

  if (loading && !data) {
    return <ActivityIndicator color={colors.accent} style={{ marginVertical: spacing.md }} />;
  }

  return (
    <View>
      <StocksSummaryTable
        rows={data?.summaries ?? []}
        totalMarketValue={data?.total_market_value ?? 0}
        busy={busy}
        onSave={async (marketValues) => {
          setBusy(true);
          try {
            const payload = await updateStockMarketValues(
              portfolioName,
              marketValues
            );
            setData(payload);
            await onPortfolioUpdated();
          } finally {
            setBusy(false);
          }
        }}
      />

      <StocksPurchasesManage
        portfolioName={portfolioName}
        data={data}
        loading={loading}
        loadError={loadError}
        onUpdated={refreshAll}
        disabled={busy}
      />

      <Text style={styles.sectionTitle}>Portfolio distributions</Text>
      <View style={styles.distTabs}>
        {DIST_TABS.map((t) => (
          <Pressable
            key={t.key}
            style={[styles.distTab, distTab === t.key && styles.distTabActive]}
            onPress={() => setDistTab(t.key)}
          >
            <Text
              style={[
                styles.distTabText,
                distTab === t.key && styles.distTabTextActive,
              ]}
            >
              {t.title}
            </Text>
          </Pressable>
        ))}
      </View>
      {distData.length > 0 ? (
        <DonutPieChart
          title={DIST_TABS.find((t) => t.key === distTab)?.title ?? ""}
          data={distData}
        />
      ) : (
        <View style={styles.emptyChart}>
          <Text style={styles.emptyChartText}>No data for this view.</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  sectionTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
  },
  distTabs: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  distTab: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    backgroundColor: colors.card,
    borderWidth: 1,
    borderColor: colors.border,
  },
  distTabActive: {
    backgroundColor: colors.accent,
    borderColor: colors.accent,
  },
  distTabText: { color: colors.text, fontSize: 12, fontWeight: "600" },
  distTabTextActive: { color: "#fff" },
  emptyChart: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: spacing.lg,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  emptyChartText: { color: colors.textMuted, textAlign: "center" },
});
