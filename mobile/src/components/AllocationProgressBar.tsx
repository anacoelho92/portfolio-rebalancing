import { useState } from "react";
import { LayoutChangeEvent, StyleSheet, Text, View } from "react-native";
import Svg, { Line } from "react-native-svg";
import { colors, spacing } from "../theme";

const PROGRESS_BLUE = "#3B82F6";
const PROGRESS_GREEN = colors.accent;
const PROGRESS_RED = colors.danger;
const TARGET_MARK = colors.warning;
/** Light stroke so dashed bands stay visible on green/blue/red fills. */
const TOLERANCE_MARK = "#E2E8F0";
const PCT_EPS = 0.05;
const TRACK_HEIGHT = 8;

type Props = {
  currentPct: number;
  targetPct: number;
  /** Band above/below target (percentage points). */
  tolerancePct?: number;
  /** Expense ratio (TER), shown in legend when provided. */
  terPct?: number;
};

function formatPct(n: number) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function formatTer(n: number) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function buildLegend(
  current: number,
  target: number,
  tolerance: number,
  terPct: number | undefined
): string {
  const parts = [`${formatPct(current)}% current`];
  if (target > 0) {
    parts.push(`${formatPct(target)}% target`);
  }
  if (target > 0 && tolerance > 0) {
    parts.push(`±${formatPct(tolerance)}%`);
  }
  if (terPct !== undefined) {
    parts.push(`TER ${formatTer(terPct)}%`);
  }
  return parts.join(" · ");
}

function clampPct(n: number) {
  return Math.min(100, Math.max(0, n));
}

function fillColorFor(
  current: number,
  target: number,
  tolerance: number
): string {
  if (target <= 0) {
    return PROGRESS_BLUE;
  }
  const tol = Math.max(0, tolerance);
  const lower = target - tol;
  const upper = target + tol;
  if (current > upper + PCT_EPS) {
    return PROGRESS_RED;
  }
  if (current + PCT_EPS >= lower && current <= upper + PCT_EPS) {
    return PROGRESS_GREEN;
  }
  return PROGRESS_BLUE;
}

function pctToX(pct: number, trackWidth: number) {
  return (clampPct(pct) / 100) * trackWidth;
}

type MarkLineProps = {
  x: number;
  dashed?: boolean;
  color: string;
};

function MarkLine({ x, dashed, color }: MarkLineProps) {
  if (!Number.isFinite(x)) {
    return null;
  }
  return (
    <Line
      x1={x}
      y1={0}
      x2={x}
      y2={TRACK_HEIGHT}
      stroke={color}
      strokeWidth={2}
      strokeDasharray={dashed ? "2,2" : undefined}
    />
  );
}

export function AllocationProgressBar({
  currentPct,
  targetPct,
  tolerancePct = 2,
  terPct,
}: Props) {
  const [trackWidth, setTrackWidth] = useState(0);
  const current = clampPct(currentPct);
  const target = clampPct(targetPct);
  const tolerance = Math.max(0, tolerancePct);
  const fillColor = fillColorFor(current, target, tolerance);

  const showMarks = target > 0 && trackWidth > 0;
  const lowerBand = clampPct(target - tolerance);
  const upperBand = clampPct(target + tolerance);

  const onTrackLayout = (e: LayoutChangeEvent) => {
    setTrackWidth(e.nativeEvent.layout.width);
  };

  return (
    <View style={styles.wrap}>
      <View style={styles.track} onLayout={onTrackLayout}>
        <View
          style={[
            styles.fill,
            { width: `${current}%`, backgroundColor: fillColor },
          ]}
        />
        {showMarks ? (
          <Svg
            width={trackWidth}
            height={TRACK_HEIGHT}
            style={styles.marks}
            pointerEvents="none"
          >
            {tolerance > 0 && lowerBand < target - PCT_EPS ? (
              <MarkLine
                x={pctToX(lowerBand, trackWidth)}
                dashed
                color={TOLERANCE_MARK}
              />
            ) : null}
            <MarkLine
              x={pctToX(target, trackWidth)}
              color={TARGET_MARK}
            />
            {tolerance > 0 && upperBand > target + PCT_EPS ? (
              <MarkLine
                x={pctToX(upperBand, trackWidth)}
                dashed
                color={TOLERANCE_MARK}
              />
            ) : null}
          </Svg>
        ) : null}
      </View>
      <Text
        style={styles.legend}
        numberOfLines={1}
        adjustsFontSizeToFit
        minimumFontScale={0.75}
      >
        {buildLegend(current, target, tolerance, terPct)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: 4 },
  track: {
    height: TRACK_HEIGHT,
    borderRadius: 4,
    backgroundColor: colors.bg,
    overflow: "hidden",
    position: "relative",
  },
  fill: {
    height: "100%",
    borderRadius: 4,
  },
  marks: {
    position: "absolute",
    left: 0,
    top: 0,
    zIndex: 2,
  },
  legend: {
    color: colors.textMuted,
    fontSize: 10,
    lineHeight: 12,
    marginTop: 2,
  },
});
