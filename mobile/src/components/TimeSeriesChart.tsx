import { StyleSheet, Text, View } from "react-native";
import Svg, { Circle, Line, Path, Polyline, Text as SvgText } from "react-native-svg";
import { colors, spacing } from "../theme";

type Point = {
  month: string;
  total_value: number;
  total_invested: number | null;
};

type Props = { data: Point[] };

const VALUE_COLOR = "#3B82F6";
const INVESTED_COLOR = "#24A16F";

const CHART_W = 320;
const CHART_H = 180;
const PAD_L = 48;
const PAD_R = 12;
const PAD_T = 16;
const PAD_B = 36;

function buildPoints(
  data: Point[],
  key: "total_value" | "total_invested",
  plotW: number,
  plotH: number,
  minY: number,
  maxY: number
): string {
  const range = maxY - minY || 1;
  return data
    .map((d, i) => {
      const raw = key === "total_value" ? d.total_value : d.total_invested;
      const yVal = raw ?? minY;
      const x = PAD_L + (i / Math.max(data.length - 1, 1)) * plotW;
      const y = PAD_T + plotH - ((yVal - minY) / range) * plotH;
      return `${x},${y}`;
    })
    .join(" ");
}

function buildAreaPath(
  data: Point[],
  plotW: number,
  plotH: number,
  minY: number,
  maxY: number
): string {
  const range = maxY - minY || 1;
  const baseline = PAD_T + plotH;
  const pts = data.map((d, i) => {
    const yVal = d.total_invested ?? minY;
    const x = PAD_L + (i / Math.max(data.length - 1, 1)) * plotW;
    const y = PAD_T + plotH - ((yVal - minY) / range) * plotH;
    return { x, y };
  });
  if (!pts.length) return "";
  const top = pts.map((p) => `${p.x},${p.y}`).join(" L ");
  const close = ` L ${pts[pts.length - 1].x},${baseline} L ${pts[0].x},${baseline} Z`;
  return `M ${top}${close}`;
}

function formatAxisY(value: number) {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(0)}k`;
  return value.toFixed(0);
}

export function TimeSeriesChart({ data }: Props) {
  if (!data.length) {
    return (
      <View style={styles.box}>
        <Text style={styles.title}>Total value vs invested</Text>
        <Text style={styles.empty}>Log an allocation to see history.</Text>
      </View>
    );
  }

  const hasInvested = data.some((d) => d.total_invested != null && d.total_invested > 0);
  const allY = data.flatMap((d) => {
    const vals = [d.total_value];
    if (d.total_invested != null) vals.push(d.total_invested);
    return vals;
  });
  const minY = 0;
  const maxY = Math.max(...allY, 1);
  const plotW = CHART_W - PAD_L - PAD_R;
  const plotH = CHART_H - PAD_T - PAD_B;

  const valuePoints = buildPoints(data, "total_value", plotW, plotH, minY, maxY);
  const investedPoints = hasInvested
    ? buildPoints(data, "total_invested", plotW, plotH, minY, maxY)
    : "";
  const areaPath = hasInvested ? buildAreaPath(data, plotW, plotH, minY, maxY) : "";

  const gridLines = [0, 0.25, 0.5, 0.75, 1].map((frac) => {
    const y = PAD_T + plotH * (1 - frac);
    const label = minY + (maxY - minY) * frac;
    return { y, label };
  });

  const labelStep = data.length <= 6 ? 1 : Math.ceil(data.length / 5);

  return (
    <View style={styles.box}>
      <Text style={styles.title}>Total value vs invested</Text>
      <View style={styles.chartWrap}>
        <Svg width="100%" height={CHART_H} viewBox={`0 0 ${CHART_W} ${CHART_H}`}>
          {gridLines.map((g, i) => (
            <Line
              key={`grid-${i}`}
              x1={PAD_L}
              y1={g.y}
              x2={CHART_W - PAD_R}
              y2={g.y}
              stroke="rgba(255,255,255,0.08)"
              strokeWidth={1}
            />
          ))}
          {gridLines.map((g, i) => (
            <SvgText
              key={`ylabel-${i}`}
              x={PAD_L - 6}
              y={g.y + 4}
              fontSize={9}
              fill={colors.textMuted}
              textAnchor="end"
            >
              {formatAxisY(g.label)}
            </SvgText>
          ))}

          {areaPath ? (
            <Path d={areaPath} fill="rgba(36, 161, 111, 0.25)" stroke="none" />
          ) : null}

          {hasInvested && investedPoints ? (
            <Polyline
              points={investedPoints}
              fill="none"
              stroke={INVESTED_COLOR}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ) : null}
          <Polyline
            points={valuePoints}
            fill="none"
            stroke={VALUE_COLOR}
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {data.map((d, i) => {
            const range = maxY - minY || 1;
            const x = PAD_L + (i / Math.max(data.length - 1, 1)) * plotW;
            const yVal = d.total_value;
            const y = PAD_T + plotH - ((yVal - minY) / range) * plotH;
            return (
              <Circle key={`v-${i}`} cx={x} cy={y} r={4} fill={VALUE_COLOR} />
            );
          })}
          {hasInvested &&
            data.map((d, i) => {
              if (d.total_invested == null) return null;
              const range = maxY - minY || 1;
              const x = PAD_L + (i / Math.max(data.length - 1, 1)) * plotW;
              const y =
                PAD_T + plotH - ((d.total_invested - minY) / range) * plotH;
              return (
                <Circle key={`i-${i}`} cx={x} cy={y} r={4} fill={INVESTED_COLOR} />
              );
            })}

          {data.map((d, i) => {
            if (i % labelStep !== 0 && i !== data.length - 1) return null;
            const x = PAD_L + (i / Math.max(data.length - 1, 1)) * plotW;
            const short = d.month.replace(/\s+\d{4}$/, "");
            return (
              <SvgText
                key={`x-${i}`}
                x={x}
                y={CHART_H - 8}
                fontSize={8}
                fill={colors.textMuted}
                textAnchor="middle"
              >
                {short.length > 8 ? short.slice(0, 7) + "…" : short}
              </SvgText>
            );
          })}
        </Svg>
      </View>
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.swatch, { backgroundColor: VALUE_COLOR }]} />
          <Text style={styles.legendText}>Total value</Text>
        </View>
        {hasInvested ? (
          <View style={styles.legendItem}>
            <View style={[styles.swatch, { backgroundColor: INVESTED_COLOR }]} />
            <Text style={styles.legendText}>Total invested</Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
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
    marginBottom: spacing.sm,
    textAlign: "center",
  },
  empty: { color: colors.textMuted, fontSize: 13, textAlign: "center" },
  chartWrap: { alignItems: "center" },
  legend: {
    flexDirection: "row",
    justifyContent: "center",
    gap: spacing.lg,
    marginTop: spacing.sm,
  },
  legendItem: { flexDirection: "row", alignItems: "center", gap: 6 },
  swatch: { width: 12, height: 3, borderRadius: 2 },
  legendText: { color: colors.textMuted, fontSize: 12 },
});
