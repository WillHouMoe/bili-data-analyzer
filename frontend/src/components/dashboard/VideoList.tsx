import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDownIcon, SearchIcon, ExternalLinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { TransposeMark } from "@/components/proof/marks";
import { Figure } from "@/components/proof/Sheet";
import { Inking, NoInk } from "@/components/proof/States";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SEP, formatCount, formatDuration, formatExact, formatPercent } from "@/lib/format";
import type { VideoSummary, PaginatedVideos } from "@/types";

type SortField =
  | "views" | "likes" | "coins" | "favorites"
  | "shares" | "danmaku" | "comments" | "published_at" | "duration";

const PAGE_SIZE = 10;

/** 一則目錄條目：緊湊態與全開態是同一個物件，展開不換頁。 */
function VideoEntry({
  video,
  index,
  creatorId,
  expanded,
  onToggle,
}: {
  video: VideoSummary;
  index: number;
  creatorId: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const tags = video.tags ? video.tags.split(",").map((s) => s.trim()).filter(Boolean) : [];
  const panelId = `entry-${video.bvid}`;

  const figures = [
    { label: t("stats.totalViews"), value: video.stats.views },
    { label: t("stats.likes"), value: video.stats.likes },
    { label: t("stats.coins"), value: video.stats.coins },
    { label: t("stats.favorites"), value: video.stats.favorites },
    { label: t("stats.shares"), value: video.stats.shares },
    { label: t("stats.danmaku"), value: video.stats.danmaku_count },
    { label: t("stats.comments"), value: video.stats.comment_count },
  ];

  return (
    <li className={cn("border-b border-rule transition-colors", expanded && "bg-paper-2")}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        aria-controls={panelId}
        className="flex w-full items-start gap-3 px-1 py-3 text-left outline-none hover:bg-paper-2 focus-visible:bg-paper-2 sm:gap-4"
      >
        <span className="w-6 shrink-0 pt-0.5 text-right text-note tabular-nums text-ink-3">
          {index}
        </span>

        <div className="relative shrink-0">
          {video.cover_url ? (
            <img
              src={video.cover_url}
              alt=""
              referrerPolicy="no-referrer"
              loading="lazy"
              className="h-[58px] w-[96px] border border-rule object-cover"
            />
          ) : (
            <div className="flex h-[58px] w-[96px] items-center justify-center border border-dashed border-rule-2 text-colophon text-ink-3">
              {t("video.noCover")}
            </div>
          )}
          {video.duration > 0 && (
            <span className="absolute right-0 bottom-0 bg-ink px-1 py-px text-colophon tabular-nums text-paper">
              {formatDuration(video.duration)}
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <p
            className={cn(
              "font-song text-ui leading-snug font-semibold",
              expanded ? "text-mark" : "text-ink",
            )}
          >
            {video.title}
          </p>
          <p className="mt-1 text-note tabular-nums text-ink-2">
            {formatCount(video.stats.views, lang)} {t("video.viewsLabel")}
            <span className="text-ink-3">{SEP}</span>
            {formatPercent(video.stats.interaction_rate)} {t("stats.interactionRate")}
            {video.published_at && (
              <>
                <span className="text-ink-3">{SEP}</span>
                {video.published_at.slice(0, 10)}
              </>
            )}
          </p>
          {tags.length > 0 && (
            <p className="mt-0.5 truncate text-colophon tracking-normal text-ink-3">
              {tags.slice(0, 5).join("、")}
            </p>
          )}
        </div>

        <ChevronDownIcon
          className={cn(
            "mt-1 size-4 shrink-0 text-ink-3 transition-transform duration-200",
            expanded && "rotate-180 text-mark",
          )}
        />
      </button>

      {expanded && (
        <div id={panelId} className="border-t border-rule px-1 pt-3 pb-4 pl-10 sm:pl-[7.5rem]">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 lg:grid-cols-7">
            {figures.map((f) => (
              <div key={f.label} title={formatExact(f.value, lang)}>
                <Figure label={f.label} value={formatCount(f.value, lang)} />
              </div>
            ))}
          </dl>

          {tags.length > 5 && (
            <p className="mt-3 text-note leading-relaxed text-ink-2">
              <span className="column-label mr-2">{t("video.tags")}</span>
              {tags.join("、")}
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
            <Link
              to={`/video/${video.bvid}?uid=${creatorId}`}
              className="text-note font-medium text-mark underline decoration-mark/40 underline-offset-[0.22em] hover:decoration-mark"
            >
              {t("video.openProof")}
            </Link>
            <a
              href={`https://www.bilibili.com/video/${video.bvid}`}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-note text-ink-2 hover:text-mark"
            >
              {t("video.openOnBilibili")}
              <ExternalLinkIcon className="size-3" />
            </a>
            <span className="colophon">{video.bvid}</span>
          </div>
        </div>
      )}
    </li>
  );
}

export default function VideoList({ creatorId }: { creatorId: number }) {
  const { t } = useTranslation();
  const [result, setResult] = useState<PaginatedVideos | null>(null);
  const [resolvedKey, setResolvedKey] = useState("");
  const [sortBy, setSortBy] = useState<SortField>("views");
  const [order, setOrder] = useState<"desc" | "asc">("desc");
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const requestKey = `${creatorId}:${sortBy}:${order}:${page}:${search}`;

  useEffect(() => {
    let active = true;
    api
      .getCreatorVideos(creatorId, {
        sort_by: sortBy,
        order,
        page: String(page),
        page_size: String(PAGE_SIZE),
        search,
      })
      .then((d) => {
        if (!active) return;
        setResult(d);
        setResolvedKey(requestKey);
      })
      .catch(() => {
        if (!active) return;
        setResult(null);
        setResolvedKey(requestKey);
      });
    return () => { active = false; };
  }, [creatorId, requestKey, page, search, sortBy, order]);

  const sortOptions: { value: SortField; label: string }[] = [
    { value: "views", label: t("stats.totalViews") },
    { value: "likes", label: t("stats.likes") },
    { value: "coins", label: t("stats.coins") },
    { value: "favorites", label: t("stats.favorites") },
    { value: "shares", label: t("stats.shares") },
    { value: "danmaku", label: t("stats.danmaku") },
    { value: "comments", label: t("stats.comments") },
    { value: "published_at", label: t("video.publishedAt") },
    { value: "duration", label: t("video.duration") },
  ];

  const totalPages = result?.total_pages ?? 1;
  const videos = result?.items ?? [];
  const loading = requestKey !== resolvedKey;
  const startIndex = (page - 1) * PAGE_SIZE;

  return (
    <div className="flex flex-col">
      <div className="flex flex-col gap-2 pb-3 sm:flex-row sm:items-center sm:justify-end">
        <div className="relative sm:w-56">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-ink-3" />
          <Input
            value={searchInput}
            onChange={(e) => { setSearchInput(e.target.value); setPage(1); }}
            placeholder={t("video.searchPlaceholder")}
            className="pl-7"
            aria-label={t("video.searchPlaceholder")}
          />
        </div>
        <div className="flex items-center gap-2">
          <Select
            value={sortBy}
            onValueChange={(v: string | null) => { if (v) { setSortBy(v as SortField); setPage(1); } }}
          >
            <SelectTrigger className="w-36" aria-label={t("video.sort")}>
              <SelectValue>{sortOptions.find((o) => o.value === sortBy)?.label}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {sortOptions.map((o) => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            onClick={() => { setOrder((p) => (p === "desc" ? "asc" : "desc")); setPage(1); }}
            aria-label={t("video.toggleOrder")}
            title={t(order === "desc" ? "video.orderDesc" : "video.orderAsc")}
          >
            <TransposeMark className={cn("size-4", order === "asc" && "-scale-y-100")} />
          </Button>
        </div>
      </div>

      {loading ? (
        <Inking className="py-12" />
      ) : videos.length === 0 ? (
        <NoInk className="py-12" label={search ? t("video.noMatch") : undefined} />
      ) : (
        <ul className="border-t border-rule-strong">
          {videos.map((v, i) => (
            <VideoEntry
              key={v.bvid}
              video={v}
              index={startIndex + i + 1}
              creatorId={creatorId}
              expanded={expanded === v.bvid}
              onToggle={() => setExpanded((cur) => (cur === v.bvid ? null : v.bvid))}
            />
          ))}
        </ul>
      )}

      {result && result.total_pages > 1 && (
        <div className="flex items-center justify-between gap-3 pt-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
          >
            {t("video.previous")}
          </Button>
          <span className="text-note tabular-nums text-ink-3">
            {t("video.pageOf", { page, total: totalPages })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || loading}
          >
            {t("video.next")}
          </Button>
        </div>
      )}
    </div>
  );
}
