import { describe, expect, test } from "vitest";
import { paginateVideos } from "@/lib/static-data";
import type { VideoSummary } from "@/types";

function video(
  bvid: string,
  title: string,
  views: number,
  publishedAt: string | null,
  tags: string | null = null,
): VideoSummary {
  return {
    bvid,
    title,
    cover_url: null,
    duration: 60,
    published_at: publishedAt,
    tags,
    is_maintained: true,
    stats: {
      views,
      likes: views / 10,
      coins: 0,
      favorites: 0,
      shares: 0,
      danmaku_count: 0,
      comment_count: 0,
      interaction_rate: 10,
    },
  };
}

const videos = [
  video("BVOLD", "Old tutorial", 100, "2026-01-01T00:00:00+08:00", "guide"),
  video("BVNEW", "New video", 300, "2026-03-01T00:00:00+08:00", "music"),
  video("BVMID", "Middle video", 200, "2026-02-01T00:00:00+08:00"),
];

describe("paginateVideos", () => {
  test("searches before sorting and paging", () => {
    const result = paginateVideos(videos, {
      search: "guide",
      sort_by: "views",
      order: "desc",
      page: "1",
      page_size: "10",
    });

    expect(result.total).toBe(1);
    expect(result.items.map((item) => item.bvid)).toEqual(["BVOLD"]);
  });

  test("sorts by a stats field and returns the requested page", () => {
    const result = paginateVideos(videos, {
      sort_by: "views",
      order: "asc",
      page: "2",
      page_size: "2",
    });

    expect(result.total_pages).toBe(2);
    expect(result.items.map((item) => item.bvid)).toEqual(["BVNEW"]);
  });

  test("defaults to newest first without mutating the snapshot array", () => {
    const originalOrder = videos.map((item) => item.bvid);
    const result = paginateVideos(videos, {});

    expect(result.items.map((item) => item.bvid)).toEqual([
      "BVNEW",
      "BVMID",
      "BVOLD",
    ]);
    expect(videos.map((item) => item.bvid)).toEqual(originalOrder);
  });
});
