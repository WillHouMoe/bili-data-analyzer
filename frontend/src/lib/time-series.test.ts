import { describe, expect, it } from "vitest";
import { toTimedSeries } from "./time-series";

describe("toTimedSeries", () => {
  it("keeps real time intervals instead of assigning equal categorical spacing", () => {
    const points = [
      { at: "2026-10-25T15:34:00+08:00", views: 20 },
      { at: "2026-10-25T13:30:00+08:00", views: 10 },
      { at: "2026-10-25T15:39:00+08:00", views: 30 },
    ];

    const series = toTimedSeries(
      points,
      (point) => point.at,
      (point) => point.views,
    );

    expect(series).toHaveLength(3);
    expect(series[1][0] - series[0][0]).toBe(124 * 60 * 1000);
    expect(series[2][0] - series[1][0]).toBe(5 * 60 * 1000);
  });
});
