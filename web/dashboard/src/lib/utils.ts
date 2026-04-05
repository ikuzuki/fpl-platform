import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatPrice(cost: number): string {
  return `\u00A3${cost.toFixed(1)}m`;
}

export function fdrClass(fdr: number): string {
  return `fdr-${Math.min(Math.max(Math.round(fdr), 1), 5)}`;
}

export function positionColor(pos: string): string {
  const colors: Record<string, string> = {
    GKP: "bg-amber-100 text-amber-800",
    DEF: "bg-blue-100 text-blue-800",
    MID: "bg-green-100 text-green-800",
    FWD: "bg-red-100 text-red-800",
  };
  return colors[pos] ?? "bg-gray-100 text-gray-800";
}

export function recommendationStyle(rec: string) {
  const styles: Record<string, { bg: string; text: string; label: string }> = {
    buy: { bg: "bg-green-100", text: "text-green-800", label: "Buy" },
    sell: { bg: "bg-red-100", text: "text-red-800", label: "Sell" },
    hold: { bg: "bg-gray-100", text: "text-gray-700", label: "Hold" },
    watch: { bg: "bg-amber-100", text: "text-amber-800", label: "Watch" },
  };
  return styles[rec] ?? styles.hold;
}

export function scoreColor(score: number): string {
  if (score >= 65) return "text-green-600";
  if (score >= 45) return "text-gray-700";
  return "text-red-500";
}
