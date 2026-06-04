import type {
  DividendMonthlyComparison,
  DividendRecord,
  DividendYearSeries,
} from "./api";

const MONTH_ABBR = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

export function buildDividendComparison(
  records: DividendRecord[],
  currentYear: number,
  filterTicker: string | null
): DividendMonthlyComparison {
  const prevYear = currentYear - 1;
  const filtered = records.filter((r) => {
    if (!r.date) return false;
    const yr = new Date(r.date).getFullYear();
    if (yr < prevYear || yr > currentYear) return false;
    if (filterTicker && r.ticker !== filterTicker) return false;
    return true;
  });

  const grouped: Record<string, number[]> = {
    [String(prevYear)]: Array(12).fill(0),
    [String(currentYear)]: Array(12).fill(0),
  };

  for (const r of filtered) {
    const d = new Date(r.date);
    const yr = String(d.getFullYear());
    const monthIdx = d.getMonth();
    if (grouped[yr] && monthIdx >= 0 && monthIdx < 12) {
      grouped[yr][monthIdx] += r.amount;
    }
  }

  const series: DividendYearSeries[] = [
    {
      year: String(prevYear),
      amounts: grouped[String(prevYear)].map((v) => Math.round(v * 100) / 100),
    },
    {
      year: String(currentYear),
      amounts: grouped[String(currentYear)].map((v) => Math.round(v * 100) / 100),
    },
  ];

  return { months: MONTH_ABBR, series };
}

export function totalsFromRecords(
  records: DividendRecord[],
  currentYear: number,
  filterTicker: string | null
): { current: number; previous: number } {
  let current = 0;
  let previous = 0;
  for (const r of records) {
    if (!r.date) continue;
    if (filterTicker && r.ticker !== filterTicker) continue;
    const yr = new Date(r.date).getFullYear();
    if (yr === currentYear) current += r.amount;
    else if (yr === currentYear - 1) previous += r.amount;
  }
  return { current, previous };
}
