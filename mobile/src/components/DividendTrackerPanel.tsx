import DateTimePicker, {
  type DateTimePickerEvent,
} from "@react-native-community/datetimepicker";
import { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  addDividend,
  DividendSummary,
  fetchDividends,
  Holding,
} from "../api";
import { buildDividendComparison, totalsFromRecords } from "../dividendChart";
import { colors, spacing } from "../theme";
import { DividendYearComparisonChart } from "./DividendYearComparisonChart";
import { Card } from "./ui/Card";
import { PrimaryButton } from "./ui/Buttons";
import { InfoBanner } from "./ui/InfoBanner";
import { SectionHeader } from "./ui/SectionHeader";
import { KpiCard } from "./KpiCard";

type Props = {
  portfolioName: string;
  holdings: Holding[];
};

function formatEuro(n: number) {
  return `€${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function toIsoDate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDisplayDate(d: Date) {
  return d.toLocaleDateString("pt-PT", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function DividendTrackerPanel({ portfolioName, holdings }: Props) {
  const [data, setData] = useState<DividendSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [dividendDate, setDividendDate] = useState(() => new Date());
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [ticker, setTicker] = useState("");
  const [amount, setAmount] = useState("");
  const [filterTicker, setFilterTicker] = useState<string | null>(null);
  const [recordOpen, setRecordOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tickers = holdings
    .map((h) => h.ticker)
    .filter((t) => t && t !== "__PLACEHOLDER__");

  const load = useCallback(async () => {
    try {
      const summary = await fetchDividends(portfolioName);
      setData(summary);
      if (!ticker && summary.tickers.length) {
        setTicker(summary.tickers[0]);
      } else if (!ticker && tickers.length) {
        setTicker(tickers[0]);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load dividends");
    } finally {
      setLoading(false);
    }
  }, [portfolioName]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const currentYear = data?.current_year ?? new Date().getFullYear();
  const comparison = data
    ? buildDividendComparison(data.records, currentYear, filterTicker)
    : null;
  const totals = data
    ? totalsFromRecords(data.records, currentYear, filterTicker)
    : { current: 0, previous: 0 };

  const filteredRecords = (data?.records ?? []).filter(
    (r) => !filterTicker || r.ticker === filterTicker
  );

  const onDateChange = (event: DateTimePickerEvent, selected?: Date) => {
    if (Platform.OS === "android") {
      setShowDatePicker(false);
    }
    if (event.type === "dismissed") {
      setShowDatePicker(false);
      return;
    }
    if (selected) {
      setDividendDate(selected);
    }
  };

  if (loading && !data) {
    return <ActivityIndicator color={colors.accent} style={{ marginVertical: spacing.lg }} />;
  }

  return (
    <View>
      <SectionHeader title="💰 Dividend Tracker" />

      <Card>
        <Pressable
          style={styles.sectionHeader}
          onPress={() => setRecordOpen((open) => !open)}
        >
          <Text style={styles.sectionTitle}>➕ Record Dividend</Text>
          <Text style={styles.chevron}>{recordOpen ? "▾" : "▸"}</Text>
        </Pressable>
        {recordOpen ? (
          <>
            <Text style={styles.fieldLabel}>Date</Text>
            <Pressable
              style={styles.dateField}
              onPress={() => setShowDatePicker(true)}
            >
              <Text style={styles.dateFieldText}>
                {formatDisplayDate(dividendDate)}
              </Text>
            </Pressable>
            {showDatePicker ? (
              <View style={styles.datePickerWrap}>
                <DateTimePicker
                  value={dividendDate}
                  mode="date"
                  display={Platform.OS === "ios" ? "spinner" : "default"}
                  onChange={onDateChange}
                  themeVariant="dark"
                />
                {Platform.OS === "ios" ? (
                  <Pressable
                    style={styles.dateDoneBtn}
                    onPress={() => setShowDatePicker(false)}
                  >
                    <Text style={styles.dateDoneText}>Done</Text>
                  </Pressable>
                ) : null}
              </View>
            ) : null}
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={styles.chipRow}>
                {tickers.map((t) => (
                  <Pressable
                    key={t}
                    style={[styles.chip, ticker === t && styles.chipActive]}
                    onPress={() => setTicker(t)}
                  >
                    <Text
                      style={[styles.chipText, ticker === t && styles.chipTextActive]}
                    >
                      {t}
                    </Text>
                  </Pressable>
                ))}
              </View>
            </ScrollView>
            <TextInput
              style={styles.input}
              keyboardType="decimal-pad"
              placeholder="Amount (€)"
              placeholderTextColor={colors.textMuted}
              value={amount}
              onChangeText={setAmount}
            />
            {error ? <Text style={styles.error}>{error}</Text> : null}
            <PrimaryButton
              label="Add record"
              loading={busy}
              onPress={async () => {
                setBusy(true);
                setError(null);
                try {
                  const summary = await addDividend(portfolioName, {
                    date: toIsoDate(dividendDate),
                    ticker,
                    amount: parseFloat(amount) || 0,
                  });
                  setData(summary);
                  setAmount("");
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Failed to add");
                } finally {
                  setBusy(false);
                }
              }}
            />
          </>
        ) : null}
      </Card>

      <Card>
        <Text style={styles.cardTitle}>📈 Monthly dividends</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          <View style={styles.chipRow}>
            <Pressable
              style={[styles.chip, !filterTicker && styles.chipActive]}
              onPress={() => setFilterTicker(null)}
            >
              <Text style={[styles.chipText, !filterTicker && styles.chipTextActive]}>
                All Data
              </Text>
            </Pressable>
            {(data?.tickers ?? []).map((t) => (
              <Pressable
                key={t}
                style={[styles.chip, filterTicker === t && styles.chipActive]}
                onPress={() => setFilterTicker(t)}
              >
                <Text
                  style={[styles.chipText, filterTicker === t && styles.chipTextActive]}
                >
                  {t}
                </Text>
              </Pressable>
            ))}
          </View>
        </ScrollView>
        <View style={styles.kpiRow}>
          <KpiCard
            label={`Total ${currentYear}`}
            value={formatEuro(totals.current)}
            accent
          />
          <KpiCard
            label={`Total ${currentYear - 1}`}
            value={formatEuro(totals.previous)}
          />
        </View>
        {comparison ? (
          <DividendYearComparisonChart comparison={comparison} />
        ) : (
          <InfoBanner message="No dividends recorded for the last two years." />
        )}
      </Card>

      <Card>
        <Pressable
          style={styles.sectionHeader}
          onPress={() => setHistoryOpen((open) => !open)}
        >
          <Text style={styles.sectionTitle}>
            Dividend History
            {filteredRecords.length > 0
              ? ` (${filteredRecords.length})`
              : ""}
          </Text>
          <Text style={styles.chevron}>{historyOpen ? "▾" : "▸"}</Text>
        </Pressable>
        {historyOpen ? (
          filteredRecords.length === 0 ? (
            <Text style={styles.empty}>No records.</Text>
          ) : (
            filteredRecords.slice(0, 50).map((r, i) => (
              <View key={`${r.date}-${r.ticker}-${i}`} style={styles.recordRow}>
                <Text style={styles.recordTicker}>
                  {r.ticker} · {r.date} · {formatEuro(r.amount)}
                </Text>
              </View>
            ))
          )
        ) : null}
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  cardTitle: { color: colors.text, fontWeight: "700", fontSize: 16, marginBottom: spacing.sm },
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 12,
    marginBottom: 4,
  },
  dateField: {
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  dateFieldText: {
    color: colors.text,
    fontSize: 14,
  },
  datePickerWrap: {
    marginBottom: spacing.sm,
    backgroundColor: colors.bg,
    borderRadius: 8,
    overflow: "hidden",
  },
  dateDoneBtn: {
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  dateDoneText: {
    color: colors.accent,
    fontWeight: "700",
    fontSize: 15,
  },
  input: {
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: spacing.sm,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: 4,
    marginBottom: spacing.sm,
  },
  chipRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
    flex: 1,
  },
  chevron: { color: colors.textMuted, fontSize: 14 },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 8,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    marginRight: spacing.sm,
  },
  chipActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.textMuted, fontSize: 12, fontWeight: "600" },
  chipTextActive: { color: "#fff" },
  kpiRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md, marginBottom: spacing.sm },
  recordRow: {
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  recordTicker: { color: colors.text, fontWeight: "600" },
  empty: { color: colors.textMuted },
  error: { color: colors.danger, marginBottom: spacing.sm },
});
