import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(cost: number): string {
  return `\u00A3${cost.toFixed(1)}m`;
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-GB").format(n);
}

export function fdrClass(fdr: number): string {
  return `fdr-${Math.min(Math.max(Math.round(fdr), 1), 5)}`;
}

export function positionColor(pos: string): string {
  const colors: Record<string, string> = {
    GKP: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
    DEF: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
    MID: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
    FWD: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  };
  return colors[pos] ?? "bg-gray-100 text-gray-800";
}

export const POS_CHART_COLORS: Record<string, string> = {
  GKP: "var(--pos-gkp)",
  DEF: "var(--pos-def)",
  MID: "var(--pos-mid)",
  FWD: "var(--pos-fwd)",
};

export const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

export const SCORE_COMPONENTS = [
  { key: "score_form", label: "Form", color: "var(--score-form)" },
  { key: "score_value", label: "Value", color: "var(--score-value)" },
  { key: "score_fixtures", label: "Fixtures", color: "var(--score-fixtures)" },
  { key: "score_xg", label: "xG", color: "var(--score-xg)" },
  { key: "score_momentum", label: "Momentum", color: "var(--score-momentum)" },
  { key: "score_ict", label: "ICT", color: "var(--score-ict)" },
  { key: "score_injury", label: "Injury", color: "var(--score-injury)" },
] as const;

export function recommendationStyle(rec: string) {
  const styles: Record<
    string,
    { bg: string; text: string; label: string; border: string }
  > = {
    buy: {
      bg: "bg-green-100 dark:bg-green-900/30",
      text: "text-green-800 dark:text-green-300",
      label: "Buy",
      border: "border-l-green-500",
    },
    sell: {
      bg: "bg-red-100 dark:bg-red-900/30",
      text: "text-red-800 dark:text-red-300",
      label: "Sell",
      border: "border-l-red-500",
    },
    hold: {
      bg: "bg-gray-100 dark:bg-gray-800/30",
      text: "text-gray-700 dark:text-gray-400",
      label: "Hold",
      border: "border-l-gray-400",
    },
    watch: {
      bg: "bg-amber-100 dark:bg-amber-900/30",
      text: "text-amber-800 dark:text-amber-300",
      label: "Watch",
      border: "border-l-amber-500",
    },
  };
  return styles[rec] ?? styles.hold;
}

export function scoreColor(score: number): string {
  if (score >= 65) return "text-green-600 dark:text-green-400";
  if (score >= 45) return "text-[var(--foreground)]";
  return "text-red-500 dark:text-red-400";
}

export function scoreBarColor(score: number): string {
  if (score >= 65) return "bg-green-500";
  if (score >= 50) return "bg-emerald-400";
  if (score >= 40) return "bg-amber-400";
  if (score >= 30) return "bg-orange-400";
  return "bg-red-500";
}

export function heatmapBg(
  value: number,
  min: number,
  max: number,
  invert = false,
): string {
  if (max === min) return "";
  let ratio = (value - min) / (max - min);
  if (invert) ratio = 1 - ratio;
  if (ratio > 0.7) return "bg-green-50 dark:bg-green-900/20";
  if (ratio < 0.3) return "bg-red-50 dark:bg-red-900/20";
  return "";
}

export function playerTier(rank: number): string | null {
  if (rank <= 20) return "Elite";
  if (rank <= 50) return "High Value";
  return null;
}

export const TOOLTIP_STYLE = {
  backgroundColor: "var(--card)",
  borderColor: "var(--border)",
  borderRadius: "0.5rem",
  fontSize: "12px",
} as const;
