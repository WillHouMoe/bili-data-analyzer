import type {
  PaginatedVideos,
  StaticSnapshot,
  VideoSummary,
} from "@/types";

export const isStaticMode = import.meta.env.VITE_STATIC_MODE === "true";

let snapshotPromise: Promise<StaticSnapshot> | null = null;

export function loadStaticSnapshot(): Promise<StaticSnapshot> {
  if (!snapshotPromise) {
    const configuredUrl = import.meta.env.VITE_STATIC_DATA_URL;
    const url =
      configuredUrl || `${import.meta.env.BASE_URL}static-data/snapshot.json`;
    snapshotPromise = fetch(url, { cache: "no-cache" }).then(async (response) => {
      if (!response.ok) {
        throw new Error(`Static data error: ${response.status}`);
      }
      const snapshot = (await response.json()) as StaticSnapshot;
      if (snapshot.schema_version !== 1) {
        throw new Error(`Unsupported static data schema: ${snapshot.schema_version}`);
      }
      return snapshot;
    });
  }
  return snapshotPromise;
}

function sortValue(video: VideoSummary, field: string): number | string {
  switch (field) {
    case "published_at":
      return video.published_at ? Date.parse(video.published_at) : Number.NEGATIVE_INFINITY;
    case "duration":
      return video.duration;
    case "likes":
      return video.stats.likes;
    case "coins":
      return video.stats.coins;
    case "favorites":
      return video.stats.favorites;
    case "shares":
      return video.stats.shares;
    case "danmaku":
      return video.stats.danmaku_count;
    case "comments":
      return video.stats.comment_count;
    case "views":
    default:
      return video.stats.views;
  }
}

export function paginateVideos(
  source: VideoSummary[],
  params: Record<string, string>,
): PaginatedVideos {
  const search = (params.search ?? "").trim().toLowerCase();
  const videos = search
    ? source.filter((video) => {
        const tags = video.tags?.toLowerCase() ?? "";
        return (
          video.title.toLowerCase().includes(search) ||
          video.bvid.toLowerCase().includes(search) ||
          tags.includes(search)
        );
      })
    : [...source];

  const field = params.sort_by || "published_at";
  const direction = params.order === "asc" ? 1 : -1;
  videos.sort((left, right) => {
    const leftValue = sortValue(left, field);
    const rightValue = sortValue(right, field);
    if (leftValue === rightValue) return left.bvid.localeCompare(right.bvid);
    return leftValue < rightValue ? -direction : direction;
  });

  const pageSize = Math.max(1, Number(params.page_size) || 20);
  const page = Math.max(1, Number(params.page) || 1);
  const total = videos.length;
  const totalPages = total ? Math.ceil(total / pageSize) : 1;
  const start = (page - 1) * pageSize;

  return {
    items: videos.slice(start, start + pageSize),
    total,
    page,
    page_size: pageSize,
    total_pages: totalPages,
  };
}

export async function readStaticPath<T>(path: string): Promise<T> {
  const snapshot = await loadStaticSnapshot();
  const [pathname, query = ""] = path.split("?");
  const parts = pathname.split("/").filter(Boolean);
  const params = new URLSearchParams(query);

  if (parts[0] === "creators") {
    const uid = parts[1];
    if (!uid) return snapshot.creators as T;

    if (parts[2] === "videos" && parts[3]) {
      const comparison = snapshot.video_comparisons[parts[3]];
      if (comparison) return comparison as T;
      throw new Error("Comparison not available");
    }
    if (parts[2] === "videos") {
      return paginateVideos(
        snapshot.creator_videos[uid] ?? [],
        Object.fromEntries(params),
      ) as T;
    }
    if (parts[2] === "stats") {
      const data = {
        summary: snapshot.creator_stats[uid],
        trend: snapshot.creator_trends[uid],
        interaction: snapshot.creator_interactions[uid],
        growth: snapshot.creator_growth[uid],
        "account-growth": snapshot.creator_account_growth[uid],
      }[parts[3] ?? ""];
      if (data !== undefined) return data as T;
    }
    const detail = snapshot.creator_details[uid];
    if (detail) return detail as T;
  }

  if (parts[0] === "videos" && parts[1]) {
    const bvid = parts[1];
    if (parts[2] === "stats" && parts[3] === "growth") {
      const growth = snapshot.video_growth[bvid];
      if (growth) return growth as T;
    }
    if (parts[2] === "stats" && parts[3] === "comparison") {
      const comparison = snapshot.video_comparisons[bvid];
      if (comparison) return comparison as T;
    }
    const detail = snapshot.video_details[bvid];
    if (detail) return detail as T;
  }

  if (parts[0] === "settings") {
    return {
      sessdata: "",
      ai_base_url: "",
      ai_api_key: "",
      ai_model: "",
      proxy_list: "",
      maintenance_mode: "windowed",
    } as T;
  }

  throw new Error(`Static dataset does not expose /${parts.join("/")}`);
}
