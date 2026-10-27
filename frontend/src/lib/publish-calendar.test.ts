import { describe, expect, it } from "vitest";
import type { VideoSummary } from "@/types";
import { buildPublishCalendar } from "./publish-calendar";

function video(publishedAt: string | null, views = 1): VideoSummary {
  return {
    bvid: publishedAt ?? "INVALID",
    title: "Video",
    cover_url: null,
    duration: 60,
    published_at: publishedAt,
    tags: null,
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
