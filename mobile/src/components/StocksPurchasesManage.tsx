import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import {
  addStockPurchase,
  deleteStockUnit,
  deleteStockUnits,
  StockPurchaseUnit,
  StockPurchasesPayload,
} from "../api";
import { colors, spacing } from "../theme";

type Props = {
  portfolioName: string;
  data: StockPurchasesPayload | null;
  loading?: boolean;
  loadError?: string | null;
  onUpdated: () => void | Promise<void>;
  disabled?: boolean;
};

function formatNum(n: number, decimals = 2) {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function StocksPurchasesManage({
  portfolioName,
  data,
  loading = false,
  loadError = null,
  onUpdated,
  disabled,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sectionOpen, setSectionOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [showAdd, setShowAdd] = useState(false);
  const [ticker, setTicker] = useState("");
  const [sector, setSector] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [unitPrice, setUnitPrice] = useState("");
  const [quantity, setQuantity] = useState("");
  const [divYield, setDivYield] = useState("");

  const toggleExpand = (ticker: string) => {
    setExpanded((prev) => ({ ...prev, [ticker]: !prev[ticker] }));
  };

  const toggleSection = () => setSectionOpen((open) => !open);

  const toggleSelect = (unitKey: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(unitKey)) next.delete(unitKey);
      else next.add(unitKey);
      return next;
    });
  };

  const selectAllTicker = (units: StockPurchaseUnit[]) => {
    const keys = units.map((u) => u.unit_key);
    const allSelected = keys.every((k) => selected.has(k));
    setSelected((prev) => {
      const next = new Set(prev);
      if (allSelected) keys.forEach((k) => next.delete(k));
      else keys.forEach((k) => next.add(k));
      return next;
    });
  };

  async function runAction(action: () => Promise<StockPurchasesPayload>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setSelected(new Set());
      await onUpdated();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function onDeleteUnit(unitKey: string) {
    Alert.alert("Remove unit", "Delete this purchase unit?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () =>
          runAction(() => deleteStockUnit(portfolioName, unitKey)),
      },
    ]);
  }

  async function onDeleteSelected(ticker: string, units: StockPurchaseUnit[]) {
    const keys = units.map((u) => u.unit_key).filter((k) => selected.has(k));
    if (!keys.length) return;
    Alert.alert("Remove units", `Delete ${keys.length} selected unit(s)?`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: () =>
          runAction(() => deleteStockUnits(portfolioName, keys)),
      },
    ]);
  }

  function unitLabel(unit: StockPurchaseUnit) {
    if (unit.fractional) {
      return `Lot ×${formatNum(unit.display_qty ?? 0, 4)}`;
    }
    return `Unit ${(unit.unit_index ?? 0) + 1}`;
  }

  if (loading && !data) {
    return <ActivityIndicator color={colors.accent} style={{ marginVertical: spacing.md }} />;
  }

  const byTicker = data?.units_by_ticker ?? {};
  const tickers = Object.keys(byTicker).sort();

  return (
    <View>
      {loadError ? <Text style={styles.error}>{loadError}</Text> : null}
      {error ? <Text style={styles.error}>{error}</Text> : null}

      <Pressable
        style={styles.addBtn}
        onPress={() => setShowAdd(true)}
        disabled={busy || disabled}
      >
        <Text style={styles.addBtnText}>+ Add purchase</Text>
      </Pressable>

      {!tickers.length ? (
        <Text style={styles.hint}>No purchases yet. Add a purchase to register buys.</Text>
      ) : null}

      <Pressable style={styles.sectionHeader} onPress={toggleSection}>
        <Text style={styles.sectionTitle}>Manage purchases</Text>
        <Text style={styles.chevron}>{sectionOpen ? "▾" : "▸"}</Text>
      </Pressable>

      {sectionOpen
        ? tickers.map((t) => {
            const units = byTicker[t] ?? [];
            const isOpen = expanded[t] === true;
            const selectedOnTicker = units.filter((u) =>
              selected.has(u.unit_key)
            );

            return (
              <View key={t} style={styles.tickerBox}>
                <Pressable
                  style={styles.tickerHeader}
                  onPress={() => toggleExpand(t)}
                >
                  <Text style={styles.tickerName}>
                    {t} — {units.length} unit{units.length !== 1 ? "s" : ""}
                  </Text>
                  <Text style={styles.chevron}>{isOpen ? "▾" : "▸"}</Text>
                </Pressable>

                {isOpen ? (
                  <View style={styles.unitsWrap}>
                    <Pressable onPress={() => selectAllTicker(units)}>
                      <Text style={styles.selectAll}>Select all</Text>
                    </Pressable>

                    {units.map((unit) => (
                      <View key={unit.unit_key} style={styles.unitRow}>
                        <Pressable
                          style={styles.checkbox}
                          onPress={() => toggleSelect(unit.unit_key)}
                        >
                          <Text style={styles.checkboxMark}>
                            {selected.has(unit.unit_key) ? "☑" : "☐"}
                          </Text>
                        </Pressable>
                        <View style={styles.unitInfo}>
                          <Text style={styles.unitLabel}>
                            {unitLabel(unit)} · {formatNum(unit.price, 2)}{" "}
                            {unit.currency || ""}
                          </Text>
                        </View>
                        <Pressable
                          onPress={() => onDeleteUnit(unit.unit_key)}
                          disabled={busy}
                          hitSlop={8}
                        >
                          <Text style={styles.deleteBtn}>✕</Text>
                        </Pressable>
                      </View>
                    ))}

                    {selectedOnTicker.length > 0 ? (
                      <Pressable
                        style={styles.deleteSelectedBtn}
                        onPress={() => onDeleteSelected(t, units)}
                        disabled={busy}
                      >
                        <Text style={styles.deleteSelectedText}>
                          Delete selected ({selectedOnTicker.length})
                        </Text>
                      </Pressable>
                    ) : null}
                  </View>
                ) : null}
              </View>
            );
          })
        : null}

      {busy ? <ActivityIndicator color={colors.accent} style={{ marginTop: spacing.sm }} /> : null}

      <Modal visible={showAdd} animationType="slide" transparent>
        <View style={styles.modalBackdrop}>
          <ScrollView contentContainerStyle={styles.modalScroll}>
            <View style={styles.modalCard}>
              <Text style={styles.modalTitle}>Add purchase</Text>
              <TextInput
                style={styles.input}
                placeholder="Ticker *"
                placeholderTextColor={colors.textMuted}
                autoCapitalize="characters"
                value={ticker}
                onChangeText={setTicker}
              />
              <TextInput
                style={styles.input}
                placeholder="Sector"
                placeholderTextColor={colors.textMuted}
                value={sector}
                onChangeText={setSector}
              />
              <TextInput
                style={styles.input}
                placeholder="Industry"
                placeholderTextColor={colors.textMuted}
                value={industry}
                onChangeText={setIndustry}
              />
              <TextInput
                style={styles.input}
                placeholder="Country"
                placeholderTextColor={colors.textMuted}
                value={country}
                onChangeText={setCountry}
              />
              <TextInput
                style={styles.input}
                placeholder="Currency"
                placeholderTextColor={colors.textMuted}
                value={currency}
                onChangeText={setCurrency}
              />
              <TextInput
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="Price (per share) *"
                placeholderTextColor={colors.textMuted}
                value={unitPrice}
                onChangeText={setUnitPrice}
              />
              <TextInput
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="Quantity *"
                placeholderTextColor={colors.textMuted}
                value={quantity}
                onChangeText={setQuantity}
              />
              <TextInput
                style={styles.input}
                keyboardType="decimal-pad"
                placeholder="Div. Yield (%)"
                placeholderTextColor={colors.textMuted}
                value={divYield}
                onChangeText={setDivYield}
              />

              <View style={styles.modalActions}>
                <Pressable
                  style={styles.cancelBtn}
                  onPress={() => setShowAdd(false)}
                >
                  <Text style={styles.cancelBtnText}>Cancel</Text>
                </Pressable>
                <Pressable
                  style={[styles.saveBtn, busy && styles.btnDisabled]}
                  disabled={busy}
                  onPress={() => {
                    runAction(() =>
                      addStockPurchase(portfolioName, {
                        ticker: ticker.trim(),
                        unit_price: parseFloat(unitPrice) || 0,
                        quantity: parseFloat(quantity) || 0,
                        sector,
                        industry,
                        country,
                        currency,
                        dividend_yield: parseFloat(divYield) || 0,
                      })
                    ).then(() => {
                      setShowAdd(false);
                      setTicker("");
                      setSector("");
                      setIndustry("");
                      setCountry("");
                      setCurrency("");
                      setUnitPrice("");
                      setQuantity("");
                      setDivYield("");
                    });
                  }}
                >
                  <Text style={styles.saveBtnText}>Save purchase</Text>
                </Pressable>
              </View>
            </View>
          </ScrollView>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  error: { color: colors.danger, marginBottom: spacing.sm },
  hint: { color: colors.textMuted, marginBottom: spacing.md, lineHeight: 20 },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
    paddingVertical: spacing.xs,
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 17,
    fontWeight: "700",
    flex: 1,
  },
  addBtn: {
    backgroundColor: colors.accent,
    borderRadius: 10,
    padding: spacing.md,
    alignItems: "center",
    marginBottom: spacing.md,
  },
  addBtnText: { color: "#fff", fontWeight: "700" },
  tickerBox: {
    backgroundColor: colors.card,
    borderRadius: 10,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  tickerHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.md,
  },
  tickerName: { color: colors.text, fontWeight: "600", flex: 1 },
  chevron: { color: colors.textMuted, fontSize: 14 },
  unitsWrap: { paddingHorizontal: spacing.md, paddingBottom: spacing.md },
  selectAll: { color: colors.accent, fontSize: 13, marginBottom: spacing.sm },
  unitRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  checkbox: { marginRight: spacing.sm },
  checkboxMark: { color: colors.text, fontSize: 18 },
  unitInfo: { flex: 1 },
  unitLabel: { color: colors.text, fontWeight: "600" },
  deleteBtn: { color: colors.danger, fontSize: 18, fontWeight: "700", padding: 4 },
  deleteSelectedBtn: { marginTop: spacing.sm },
  deleteSelectedText: { color: colors.danger, fontWeight: "600" },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "flex-end",
  },
  modalScroll: { flexGrow: 1, justifyContent: "flex-end" },
  modalCard: {
    backgroundColor: colors.card,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: spacing.lg,
    maxHeight: "90%",
  },
  modalTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "700",
    marginBottom: spacing.md,
  },
  input: {
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: spacing.sm,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: 4,
  },
  modalActions: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  cancelBtn: {
    flex: 1,
    padding: spacing.md,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
  },
  cancelBtnText: { color: colors.textMuted, fontWeight: "600" },
  saveBtn: {
    flex: 1,
    padding: spacing.md,
    borderRadius: 10,
    backgroundColor: colors.accent,
    alignItems: "center",
  },
  saveBtnText: { color: "#fff", fontWeight: "700" },
  btnDisabled: { opacity: 0.6 },
});
