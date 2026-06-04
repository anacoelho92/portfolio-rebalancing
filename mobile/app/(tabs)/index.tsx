import { router } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useFocusEffect } from "expo-router";
import {
  fetchPortfolios,
  logout,
  portfolioLoadHint,
  PortfolioDetail,
  PortfolioListItem,
} from "../../src/api";
import { GlobalOverviewSection } from "../../src/components/GlobalOverviewSection";
import { Card } from "../../src/components/ui/Card";
import {
  formatPortfolioNavLabel,
  portfolioMenuItems,
} from "../../src/portfolioNav";
import { colors, spacing } from "../../src/theme";

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function PortfoliosScreen() {
  const [items, setItems] = useState<PortfolioListItem[]>([]);
  const [overview, setOverview] = useState<PortfolioDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const menuItems = useMemo(() => portfolioMenuItems(items), [items]);

  const load = useCallback(async () => {
    setError(null);
    setHint(null);
    try {
      const data = await fetchPortfolios();
      setItems(data.portfolios);
      setOverview(data.overview);
      if (portfolioMenuItems(data.portfolios).length === 0) {
        setHint(await portfolioLoadHint());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  async function onLogout() {
    await logout();
    router.replace("/");
  }

  function openPortfolio(item: PortfolioListItem) {
    router.push({
      pathname: "/portfolio/[name]",
      params: { name: encodeURIComponent(item.name) },
    });
  }

  if (loading && items.length === 0 && !overview) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerLabel}>Portfolio Manager</Text>
        <Pressable onPress={onLogout} style={styles.logoutWrap}>
          <Text style={styles.logout}>Logout</Text>
        </Pressable>
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <FlatList
        data={menuItems}
        keyExtractor={(item) => item.name}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={load} tintColor={colors.accent} />
        }
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={
          <GlobalOverviewSection detail={overview} loading={loading} />
        }
        renderItem={({ item }) => (
          <Pressable onPress={() => openPortfolio(item)}>
            <Card style={styles.menuCard}>
              <View style={styles.rowInner}>
                <View style={styles.rowText}>
                  <Text style={styles.rowTitle}>
                    {formatPortfolioNavLabel(item)}
                  </Text>
                </View>
                <Text style={styles.rowValue}>
                  {formatEuro(item.total_value)}
                </Text>
              </View>
            </Card>
          </Pressable>
        )}
        ListEmptyComponent={
          menuItems.length === 0 && !loading ? (
            <View style={styles.emptyWrap}>
              <Text style={styles.empty}>No portfolios found.</Text>
              {hint ? <Text style={styles.hint}>{hint}</Text> : null}
            </View>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  centered: {
    flex: 1,
    backgroundColor: colors.bg,
    justifyContent: "center",
    alignItems: "center",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.lg,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerLabel: { color: colors.text, fontSize: 18, fontWeight: "800" },
  logoutWrap: { padding: spacing.xs },
  logout: { color: colors.text, fontSize: 14, opacity: 0.8 },
  listContent: { padding: spacing.md, paddingBottom: spacing.xl },
  menuCard: { marginBottom: spacing.sm },
  rowInner: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  rowText: { flex: 1, marginRight: spacing.md },
  rowTitle: { color: colors.text, fontSize: 16, fontWeight: "600" },
  rowValue: { color: colors.accent, fontWeight: "700", fontSize: 15 },
  error: { color: colors.danger, paddingHorizontal: spacing.md, marginBottom: spacing.sm },
  emptyWrap: { marginTop: spacing.md, paddingHorizontal: spacing.sm },
  empty: { color: colors.textMuted, textAlign: "center" },
  hint: {
    color: colors.textMuted,
    textAlign: "center",
    marginTop: spacing.md,
    fontSize: 13,
    lineHeight: 20,
  },
});
