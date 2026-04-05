import { describe, it, expect } from "vitest";
import {
  cn,
  formatPrice,
  formatNumber,
  fdrClass,
  positionColor,
  recommendationStyle,
  scoreColor,
  scoreBarColor,
  heatmapBg,
  playerTier,
  POS_CHART_COLORS,
  CHART_COLORS,
  SCORE_COMPONENTS,
} from "./utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("px-2", "py-3")).toBe("px-2 py-3");
  });

  it("handles conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("resolves Tailwind conflicts", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});

describe("formatPrice", () => {
  it("formats price in pounds with 1 decimal", () => {
    expect(formatPrice(13.0)).toBe("\u00A313.0m");
    expect(formatPrice(5.5)).toBe("\u00A35.5m");
  });

  it("handles integer prices", () => {
    expect(formatPrice(10)).toBe("\u00A310.0m");
  });
});

describe("formatNumber", () => {
  it("formats numbers with EN-GB locale", () => {
    expect(formatNumber(1234)).toBe("1,234");
    expect(formatNumber(0)).toBe("0");
  });
});

describe("fdrClass", () => {
  it("returns correct FDR class for valid values", () => {
    expect(fdrClass(1)).toBe("fdr-1");
    expect(fdrClass(3)).toBe("fdr-3");
    expect(fdrClass(5)).toBe("fdr-5");
  });

  it("clamps to valid range", () => {
    expect(fdrClass(0)).toBe("fdr-1");
    expect(fdrClass(10)).toBe("fdr-5");
    expect(fdrClass(-1)).toBe("fdr-1");
  });

  it("rounds decimals", () => {
    expect(fdrClass(2.4)).toBe("fdr-2");
    expect(fdrClass(2.6)).toBe("fdr-3");
  });
});

describe("positionColor", () => {
  it("returns correct Tailwind classes for each position", () => {
    expect(positionColor("GKP")).toContain("bg-amber");
    expect(positionColor("DEF")).toContain("bg-blue");
    expect(positionColor("MID")).toContain("bg-green");
    expect(positionColor("FWD")).toContain("bg-red");
  });

  it("returns fallback for unknown position", () => {
    expect(positionColor("???")).toContain("bg-gray");
  });
});

describe("recommendationStyle", () => {
  it("returns correct styles for buy", () => {
    const style = recommendationStyle("buy");
    expect(style.label).toBe("Buy");
    expect(style.border).toContain("green");
  });

  it("returns correct styles for sell", () => {
    const style = recommendationStyle("sell");
    expect(style.label).toBe("Sell");
    expect(style.border).toContain("red");
  });

  it("returns hold for unknown recommendation", () => {
    const style = recommendationStyle("unknown");
    expect(style.label).toBe("Hold");
  });
});

describe("scoreColor", () => {
  it("returns green for high scores", () => {
    expect(scoreColor(70)).toContain("green");
  });

  it("returns default for medium scores", () => {
    expect(scoreColor(50)).toContain("foreground");
  });

  it("returns red for low scores", () => {
    expect(scoreColor(30)).toContain("red");
  });
});

describe("scoreBarColor", () => {
  it("returns green-500 for 65+", () => {
    expect(scoreBarColor(65)).toBe("bg-green-500");
  });

  it("returns emerald for 50-64", () => {
    expect(scoreBarColor(55)).toBe("bg-emerald-400");
  });

  it("returns amber for 40-49", () => {
    expect(scoreBarColor(45)).toBe("bg-amber-400");
  });

  it("returns orange for 30-39", () => {
    expect(scoreBarColor(35)).toBe("bg-orange-400");
  });

  it("returns red for <30", () => {
    expect(scoreBarColor(20)).toBe("bg-red-500");
  });
});

describe("heatmapBg", () => {
  it("returns green for high values", () => {
    expect(heatmapBg(90, 0, 100)).toContain("green");
  });

  it("returns red for low values", () => {
    expect(heatmapBg(10, 0, 100)).toContain("red");
  });

  it("returns empty for middle values", () => {
    expect(heatmapBg(50, 0, 100)).toBe("");
  });

  it("returns empty when min equals max", () => {
    expect(heatmapBg(5, 5, 5)).toBe("");
  });

  it("inverts when invert flag is set", () => {
    expect(heatmapBg(90, 0, 100, true)).toContain("red");
    expect(heatmapBg(10, 0, 100, true)).toContain("green");
  });
});

describe("playerTier", () => {
  it("returns Elite for ranks 1-20", () => {
    expect(playerTier(1)).toBe("Elite");
    expect(playerTier(20)).toBe("Elite");
  });

  it("returns High Value for ranks 21-50", () => {
    expect(playerTier(21)).toBe("High Value");
    expect(playerTier(50)).toBe("High Value");
  });

  it("returns null for ranks above 50", () => {
    expect(playerTier(51)).toBeNull();
    expect(playerTier(200)).toBeNull();
  });
});

describe("design system constants", () => {
  it("POS_CHART_COLORS has all 4 positions", () => {
    expect(Object.keys(POS_CHART_COLORS)).toEqual(["GKP", "DEF", "MID", "FWD"]);
    Object.values(POS_CHART_COLORS).forEach((color) => {
      expect(color).toMatch(/^var\(--pos-/);
    });
  });

  it("CHART_COLORS has 5 entries using CSS vars", () => {
    expect(CHART_COLORS).toHaveLength(5);
    CHART_COLORS.forEach((color) => {
      expect(color).toMatch(/^var\(--chart-/);
    });
  });

  it("SCORE_COMPONENTS has 7 entries using CSS vars", () => {
    expect(SCORE_COMPONENTS).toHaveLength(7);
    SCORE_COMPONENTS.forEach((comp) => {
      expect(comp.color).toMatch(/^var\(--score-/);
      expect(comp.key).toMatch(/^score_/);
      expect(comp.label).toBeTruthy();
    });
  });
});
