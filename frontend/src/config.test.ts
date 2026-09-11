import { describe, it, expect } from "vitest";
import {
  formatINR,
  isEstimatedPriceSource,
} from "./config";

describe("formatINR", () => {
  it("formats Indian-style thousands separators", () => {
    expect(formatINR(1000)).toBe("₹1,000");
    expect(formatINR(24000)).toBe("₹24,000");
    expect(formatINR(150000)).toBe("₹1,50,000");
  });

  it("handles zero and decimals", () => {
    expect(formatINR(0)).toBe("₹0");
    expect(formatINR(15999)).toBe("₹15,999");
  });
});

describe("isEstimatedPriceSource", () => {
  it("flags unverified / closest-match sources", () => {
    expect(
      isEstimatedPriceSource(
        "Random Forest ML + Dataset (closest match, unverified)"
      )
    ).toBe(true);
    expect(
      isEstimatedPriceSource("Dataset match (unverified)")
    ).toBe(true);
  });

  it("does not flag concrete sources", () => {
    expect(
      isEstimatedPriceSource("Gemini Market Data")
    ).toBe(false);
    expect(isEstimatedPriceSource("Registered device")).toBe(
      false
    );
    expect(isEstimatedPriceSource(undefined)).toBe(false);
    expect(isEstimatedPriceSource("")).toBe(false);
  });
});
