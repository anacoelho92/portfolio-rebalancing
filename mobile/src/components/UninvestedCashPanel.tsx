import { useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { savePortfolio } from "../api";
import type { Holding } from "../api";
import { colors, spacing } from "../theme";
import { Card } from "./ui/Card";
import { PrimaryButton } from "./ui/Buttons";
import { InfoBanner } from "./ui/InfoBanner";
import { SectionHeader } from "./ui/SectionHeader";

type Props = {
  portfolioName: string;
  uninvestedCash: number;
  holdings: Holding[];
  onSaved: () => void;
};

function formatEuro(value: number) {
  return `€${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function UninvestedCashPanel({
  portfolioName,
  uninvestedCash,
  holdings,
  onSaved,
}: Props) {
  const [value, setValue] = useState(String(uninvestedCash));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const num = parseFloat(value) || 0;

  async function onSave() {
    setBusy(true);
    setError(null);
    setSuccess(false);
    try {
      await savePortfolio(portfolioName, {
        holdings,
        uninvested_cash: num,
      });
      setSuccess(true);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <SectionHeader title="🪙 Uninvested Cash Balance" />
      {num > 0 ? (
        <InfoBanner
          variant="warning"
          message={`Currently saved balance: ${formatEuro(num)}`}
        />
      ) : (
        <Text style={styles.metric}>Currently saved: {formatEuro(0)}</Text>
      )}
      <TextInput
        style={styles.input}
        keyboardType="decimal-pad"
        placeholder="Cash balance (€)"
        placeholderTextColor={colors.textMuted}
        value={value}
        onChangeText={setValue}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      {success ? (
        <InfoBanner variant="success" message="Cash balance saved successfully." />
      ) : null}
      <PrimaryButton label="💾 Save" onPress={onSave} loading={busy} />
    </Card>
  );
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: colors.bg,
    borderRadius: 8,
    padding: spacing.sm,
    color: colors.text,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: 4,
    marginBottom: spacing.md,
  },
  metric: { color: colors.text, fontSize: 16, marginBottom: spacing.md },
  error: { color: colors.danger, marginBottom: spacing.sm },
});
