import { ScrollView, StyleSheet, Text, View } from "react-native";
import type { RecommendationRow } from "../api";
import { colors, spacing } from "../theme";

const SAFE_LIQUIDITY = "Safe Liquidity";

type Props = {
  rows: RecommendationRow[];
};

function formatNum(n: number, decimals = 2) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatEuro(n: number) {
  return `€${formatNum(n)}`;
}

function getInvestment(r: RecommendationRow): number {
  const raw =
    r.investment ??
    (r as RecommendationRow & { Investment?: number }).Investment;
  const n = typeof raw === "number" ? raw : Number(raw);
  return Number.isFinite(n) ? n : 0;
}

type Col = {
  key: string;
  label: string;
  width: number;
  align: "left" | "right";
  render: (r: RecommendationRow) => string;
  highlight?: (r: RecommendationRow) => boolean;
  pinned?: boolean;
};

const columns: Col[] = [
  {
    key: "stock",
    label: "Stock",
    width: 92,
    align: "left",
    pinned: true,
    render: (r) => r.stock,
  },
  {
    key: "inv",
    label: "Invest €",
    width: 92,
    align: "right",
    pinned: true,
    render: (r) => formatEuro(getInvestment(r)),
    highlight: (r) => getInvestment(r) > 0.005,
  },
  {
    key: "cv",
    label: "Current €",
    width: 88,
    align: "right",
    render: (r) => formatEuro(r.current_value),
  },
  {
    key: "cp",
    label: "Current %",
    width: 72,
    align: "right",
    render: (r) => `${formatNum(r.current_pct)}%`,
  },
  {
    key: "tp",
    label: "Target %",
    width: 72,
    align: "right",
    render: (r) => `${formatNum(r.target_pct)}%`,
  },
  {
    key: "nv",
    label: "New €",
    width: 88,
    align: "right",
    render: (r) => formatEuro(r.new_value),
  },
  {
    key: "np",
    label: "New %",
    width: 64,
    align: "right",
    render: (r) => `${formatNum(r.new_pct)}%`,
  },
];

const pinnedCols = columns.filter((c) => c.pinned);
const scrollCols = columns.filter((c) => !c.pinned);
const scrollWidth = scrollCols.reduce((s, c) => s + c.width, 0);
const pinnedWidth = pinnedCols.reduce((s, c) => s + c.width, 0);

function HeaderCells({ cols }: { cols: Col[] }) {
  return (
    <>
      {cols.map((col) => (
        <Text
          key={col.key}
          style={[styles.headerCell, { width: col.width, textAlign: col.align }]}
        >
          {col.label}
        </Text>
      ))}
    </>
  );
}

function DataCells({ cols, row }: { cols: Col[]; row: RecommendationRow }) {
  return (
    <>
      {cols.map((col) => {
        const isInvest = col.key === "inv" && col.highlight?.(row);
        const isSafe = row.stock === SAFE_LIQUIDITY && isInvest;
        return (
          <View
            key={col.key}
            style={[
              styles.cell,
              { width: col.width },
              isInvest && {
                backgroundColor: isSafe
                  ? colors.safeLiquidity
                  : colors.investHighlight,
              },
            ]}
          >
            <Text
              style={[
                styles.cellText,
                col.key === "stock" && styles.stockText,
                { textAlign: col.align },
                isInvest && styles.cellTextHighlight,
              ]}
              numberOfLines={1}
              ellipsizeMode="tail"
              adjustsFontSizeToFit={col.key === "inv"}
              minimumFontScale={0.85}
            >
              {col.render(row)}
            </Text>
          </View>
        );
      })}
    </>
  );
}

export function AllocationTable({ rows }: Props) {
  const visible = rows.filter((r) => !r.stock.toUpperCase().includes("WTEQ"));

  return (
    <View style={styles.wrap}>
      <Text style={styles.title}>Investment recommendations</Text>

      <View style={styles.tableRow}>
        <View style={[styles.pinnedPane, { width: pinnedWidth }]}>
          <View style={styles.headerRow}>
            <HeaderCells cols={pinnedCols} />
          </View>
          {visible.map((row) => (
            <View key={`pin-${row.stock}`} style={styles.dataRow}>
              <DataCells cols={pinnedCols} row={row} />
            </View>
          ))}
        </View>

        <ScrollView
          horizontal
          showsHorizontalScrollIndicator
          style={styles.scrollPane}
          contentContainerStyle={{ minWidth: scrollWidth }}
        >
          <View>
            <View style={styles.headerRow}>
              <HeaderCells cols={scrollCols} />
            </View>
            {visible.map((row) => (
              <View key={`scroll-${row.stock}`} style={styles.dataRow}>
                <DataCells cols={scrollCols} row={row} />
              </View>
            ))}
          </View>
        </ScrollView>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.md,
  },
  title: {
    color: colors.text,
    fontWeight: "700",
    fontSize: 16,
    marginBottom: spacing.xs,
  },
  tableRow: {
    flexDirection: "row",
  },
  pinnedPane: {
    borderRightWidth: 1,
    borderRightColor: colors.border,
    paddingRight: spacing.xs,
  },
  scrollPane: {
    flex: 1,
  },
  headerRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingBottom: spacing.sm,
    marginBottom: spacing.xs,
  },
  headerCell: {
    color: colors.text,
    fontSize: 11,
    fontWeight: "700",
    paddingHorizontal: 4,
  },
  dataRow: {
    flexDirection: "row",
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    paddingVertical: spacing.sm,
    height: 44,
    alignItems: "center",
  },
  cell: {
    paddingHorizontal: 4,
    justifyContent: "center",
    borderRadius: 4,
  },
  cellText: {
    color: colors.text,
    fontSize: 12,
  },
  stockText: {
    fontWeight: "600",
    fontSize: 11,
  },
  cellTextHighlight: {
    color: "#fff",
    fontWeight: "700",
  },
});
