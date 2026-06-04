import { Fragment } from "react";
import { StyleSheet, Text, View } from "react-native";
import Svg, { Line, Rect, Text as SvgText } from "react-native-svg";
import type { DividendMonthlyComparison } from "../api";
import { chartPalette, colors, spacing } from "../theme";

type Props = {
  comparison: DividendMonthlyComparison;
};

const CHART_W = 340;
const CHART_H = 200;
const PAD_L = 40;
const PAD_R = 8;
const PAD_T = 12;
const PAD_B = 32;

function formatEuro(n: number) {
  if (n >= 1000) return `€${(n / 1000).toFixed(1)}k`;
  return `€${n.toFixed(0)}`;
}

function formatBarLabel(n: number) {
  if (n <= 0) return "";
  return `€${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export function DividendYearComparisonChart({ comparison }: Props) {
  const { months, series } = comparison;
  const nMonths = months.length || 12;
  const nSeries = Math.max(series.length, 1);
  const allAmounts = series.flatMap((s) => s.amounts);
  const maxY = Math.max(...allAmounts, 1);
  const hasData = allAmounts.some((v) => v > 0);

  const plotW = CHART_W - PAD_L - PAD_R;
  const plotH = CHART_H - PAD_T - PAD_B;
  const groupW = plotW / nMonths;
  const barGap = 2;
  const barW = Math.max(4, (groupW - barGap * (nSeries + 1)) / nSeries);

  const gridLines = [0, 0.5, 1].map((frac) => ({
    y: PAD_T + plotH * (1 - frac),
    label: maxY * frac,
  }));

  return (
    <View style={styles.box}>
      <Text style={styles.title}>Dividends Received (Yearly Comparison)</Text>
      {!hasData ? (
        <Text style={styles.empty}>No dividends in this period.</Text>
      ) : (
        <View style={styles.chartWrap}>
          <Svg width="100%" height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
            {gridLines.map((g, i) => (
              <Fragment key={`grid-${i}`}>
                <Line
                  x1={PAD_L}
                  y1={g.y}
                  x2={CHART_W - PAD_R}
                  y2={g.y}
                  stroke="rgba(255,255,255,0.08)"
                  strokeWidth={1}
                />
                <SvgText
                  x={PAD_L - 4}
                  y={g.y + 4}
                  fontSize={9}
                  fill={colors.textMuted}
                  textAnchor="end"
                >
                  {formatEuro(g.label)}
                </SvgText>
              </Fragment>
            ))}

            {months.map((month, mi) => {
              const groupX = PAD_L + mi * groupW;
              return (
                <Fragment key={month}>
                  {series.map((s, si) => {
                    const amount = s.amounts[mi] ?? 0;
                    const barH = (amount / maxY) * plotH;
                    const x = groupX + barGap + si * (barW + barGap);
                    const y = PAD_T + plotH - barH;
                    const color = chartPalette[si % chartPalette.length];
                    return (
                      <Fragment key={`${month}-${s.year}`}>
                        <Rect
                          x={x}
                          y={y}
                          width={barW}
                          height={Math.max(barH, 0)}
                          fill={color}
                          rx={2}
                        />
                        {amount > 0 && barH > 14 ? (
                          <SvgText
                            x={x + barW / 2}
                            y={y - 2}
                            fontSize={7}
                            fill={colors.text}
                            textAnchor="middle"
                          >
                            {formatBarLabel(amount)}
                          </SvgText>
                        ) : null}
                      </Fragment>
                    );
                  })}
                  <SvgText
                    x={groupX + groupW / 2}
                    y={CHART_H - 8}
                    fontSize={9}
                    fill={colors.textMuted}
                    textAnchor="middle"
                  >
                    {month}
                  </SvgText>
                </Fragment>
              );
            })}
          </Svg>
        </View>
      )}
      <View style={styles.legend}>
        {series.map((s, i) => (
          <View key={s.year} style={styles.legendItem}>
            <View
              style={[
                styles.swatch,
                { backgroundColor: chartPalette[i % chartPalette.length] },
              ]}
            />
            <Text style={styles.legendText}>{s.year}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: { marginTop: spacing.sm },
  title: {
    color: colors.text,
    fontWeight: "700",
    fontSize: 14,
    marginBottom: spacing.sm,
    textAlign: "center",
  },
  empty: {
    color: colors.textMuted,
    fontSize: 13,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  chartWrap: { alignItems: "center" },
  legend: {
    flexDirection: "row",
    justifyContent: "center",
    flexWrap: "wrap",
    gap: spacing.md,
    marginTop: spacing.sm,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  swatch: { width: 14, height: 14, borderRadius: 3 },
  legendText: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
});
