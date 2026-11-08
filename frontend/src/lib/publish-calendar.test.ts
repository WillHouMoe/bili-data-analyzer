import { describe, expect, it } from "vitest";
import type { VideoSummary } from "@/types";
import {
  buildPublishCalendar,
  buildPublishCalendarSummary,
  calendarYearOptions,
} from "./publish-calendar";

function video(publishedAt: string | null, views = 1): VideoSummary {
  return {
    bvid: publishedAt ?? "INVALID",
    title: "Video",
    cover_url: null,
    duration: 60,
    published_at: publishedAt,
    tags: null,
    is_maintained: true,
    stats: {
      views,
      likes: 0,
      coins: 0,
      favorites: 0,
      shares: 0,
      danmaku_count: 0,
      comment_count: 0,
      interaction_rate: 0,
    },
  };
}

describe("buildPublishCalendar", () => {
  it("builds every day in the inclusive query range and aligns weeks on Sunday", () => {
    const calendar = buildPublishCalendar(
      "2026-07-25",
      "2026-10-25",
      [video("2026-10-21T03:00:00Z")],
    );
    const days = calendar.weeks.flatMap((week) => week.days.filter((day) => day !== null));

    expect(calendar.totalDays).toBe(93);
    expect(days).toHaveLength(93);
    expect(calendar.weeks[0].days[6]?.date).toBe("2026-07-25");
    expect(days.at(-1)?.date).toBe("2026-10-25");
  });

  it("groups same-day videos and scales color by the day's most-viewed video", () => {
    const calendar = buildPublishCalendar(
      "2026-10-01",
      "2026-10-31",
      [
        video("2026-10-21T01:00:00Z", 4000),
        video("2026-10-21T09:00:00Z", 12000),
        video("2026-10-22T03:00:00Z", 3000),
        video("2026-09-30T03:00:00Z"),
        video("not-a-date"),
      ],
    );
    const days = calendar.weeks.flatMap((week) => week.days.filter((day) => day !== null));
    const october21 = days.find((day) => day.date === "2026-10-21");
    const october22 = days.find((day) => day.date === "2026-10-22");

    expect(calendar.publishedCount).toBe(3);
    expect(october21).toMatchObject({ count: 2, maxViews: 12000, level: 4 });
    expect(october22).toMatchObject({ count: 1, maxViews: 3000, level: 1 });
  });
});

describe("calendarYearOptions", () => {
  it("offers data-bearing years only when the library spans over one year", () => {
    const videos = [
      video("2024-02-01T03:00:00Z"),
      video("2025-04-01T03:00:00Z"),
      video("2026-10-21T03:00:00Z"),
    ];

    expect(
      calendarYearOptions("2024-01-01", "2025-01-01", videos),
    ).toEqual([]);
    expect(
      calendarYearOptions("2024-01-01", "2026-10-21", videos),
    ).toEqual([2026, 2025, 2024]);
  });
});

describe("buildPublishCalendarSummary", () => {
  it("summarizes only the selected date range", () => {
    const summary = buildPublishCalendarSummary(
      "2026-01-01",
      "2026-12-31",
      [
        video("2026-01-05T03:00:00Z", 100),
        video("2026-01-15T03:00:00Z", 200),
        video("2026-03-01T03:00:00Z", 50),
        video("2025-12-31T03:00:00Z", 900),
      ],
      new Date("2026-10-27T00:00:00Z"),
    );

    expect(summary).toMatchObject({
      publishedCount: 3,
      activeDays: 3,
      longestGapDays: 45,
      busiestMonth: { month: "2026-01", count: 2 },
      totalViews: 350,
      throughDate: "2026-10-27",
    });
    expect(summary?.topVideo?.stats.views).toBe(200);
    expect(summary?.topVideos.map((item) => item.stats.views)).toEqual([
      200,
      100,
      50,
    ]);
    expect(summary?.averagePerMonth).toBeCloseTo(0.3);
  });
});
