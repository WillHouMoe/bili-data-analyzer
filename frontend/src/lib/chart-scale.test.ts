import { describe, expect, it } from "vitest";
import { autoScaleRange, scaledDecimal, scaledNumber } from "./chart-scale";

describe("autoScaleRange", () => {
  it("narrows a high-valued series instead of forcing zero", () => {
    const range = autoScaleRange([14_800_000, 14_850_000, 14_874_728]);

    expect(range.min).toBeGreaterThan(14_000_000);
    expect(range.max).toBeGreaterThan(14_874_728);
  });

  it("keeps a single value centered with visible headroom", () => {
    const range = autoScaleRange([88]);

    expect(range.min).toBeLessThan(88);
    expect(range.max).toBeGreaterThan(88);
  });

  it("can opt back into a zero-based axis", () => {
    expect(autoScaleRange([80, 100], { includeZero: true }).min).toBe(0);
  });

  it("never invents a negative minimum for positive data", () => {
    expect(autoScaleRange([0.2, 0.3, 0.4]).min).toBeGreaterThanOrEqual(0);
  });

  it("keeps compact labels distinct after narrowing a large axis", () => {
    expect(scaledNumber(0, 1)).toBe("0");
    expect(scaledNumber(14_850_000, 30_000)).not.toBe(
      scaledNumber(14_870_000, 30_000),
    );
    expect(scaledNumber(14_800_000, 100_000)).not.toBe(
      scaledNumber(14_820_000, 100_000),
    );
  });

  it("adds precision to narrow percentage ranges", () => {
    expect(scaledDecimal(8.42, 0.1)).toBe("8.42");
    expect(scaledDecimal(8.4, 0.05)).toBe("8.40");
  });
});
