import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import type {
  CreatorDetail,
  StatsSummary,
  VideoSummary,
} from "@/types";
import { formatCount, formatExact, formatPercent } from "@/lib/format";
import Masthead from "@/components/proof/Masthead";
import { Section, Column, Columns, Colophon, InkIn } from "@/components/proof/Sheet";
import { BlankSheet, PressRun, type Stage } from "@/components/proof/States";
import { Button } from "@/components/ui/button";
import Lede from "@/components/dashboard/Lede";
import Ledger, { type LedgerRow } from "@/components/proof/Ledger";
import ViewsTrendChart from "@/components/dashboard/ViewsTrendChart";
import InteractionChart from "@/components/dashboard/InteractionChart";
import ScatterChart from "@/components/dashboard/ScatterChart";
import DurationChart from "@/components/dashboard/DurationChart";
import PublishCalendar from "@/components/dashboard/PublishCalendar";
import VideoList from "@/components/dashboard/VideoList";
import AIPanel from "@/components/dashboard/AIPanel";
import VideoNote, { type VideoNoteRow } from "@/components/dashboard/VideoNote";
import NewQueryDialog from "@/components/dashboard/NewQueryDialog";
import RankingHighlights from "@/components/dashboard/RankingHighlights";
import CreatorStatsPanel from "@/components/dashboard/CreatorStatsPanel";
import CreatorAccountGrowthCharts from "@/components/dashboard/CreatorAccountGrowthCharts";
import type { PublishCalendarDay } from "@/lib/publish-calendar";

/** Ledger key -> the API sort field and the per-video figure it prints. */
const LEDGER_METRICS: Record<
  string,
  { sortBy: string; value: (v: VideoSummary) => number; percent?: boolean }
> = {
  views: { sortBy: "views", value: (v) => v.stats.views },
  likes: { sortBy: "likes", value: (v) => v.stats.likes },
  coins: { sortBy: "coins", value: (v) => v.stats.coins },
  favorites: { sortBy: "favorites", value: (v) => v.stats.favorites },
  shares: { sortBy: "shares", value: (v) => v.stats.shares },
  danmaku: { sortBy: "danmaku", value: (v) => v.stats.danmaku_count },
  comments: { sortBy: "comments", value: (v) => v.stats.comment_count },
  videos: { sortBy: "published_at", value: (v) => v.stats.views },
  rate: { sortBy: "views", value: (v) => v.stats.interaction_rate, percent: true },
};

/** 版面上被圈起來的那一項，供各欄自己上朱批。 */
type Selection =
  | { kind: "ledger"; key: string }
  | { kind: "date"; key: string }
  | { kind: "band"; key: string }
  | null;

interface NoteState {
  subject: string;
  meta?: string;
  rows: VideoNoteRow[];
  loading: boolean;
}

async function fetchAllCreatorVideos(creatorId: number): Promise<VideoSummary[]> {
  const first = await api.getCreatorVideos(creatorId, {
    sort_by: "views",
    order: "desc",
    page: "1",
    page_size: "100",
  });
  if (first.total_pages <= 1) return first.items;

  const remaining = await Promise.all(
    Array.from({ length: first.total_pages - 1 }, (_, index) =>
      api.getCreatorVideos(creatorId, {
        sort_by: "views",
        order: "desc",
        page: String(index + 2),
        page_size: "100",
      }),
    ),
  );
  return [first, ...remaining].flatMap((page) => page.items);
}

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { uid: uidStr } = useParams<{ uid?: string }>();
  const creatorId = uidStr ? Number(uidStr) : null;
  const location = useLocation();
  const fetchStartedAt =
    (location.state as { fetchStartedAt?: number } | null)?.fetchStartedAt ?? 0;

  const [detail, setDetail] = useState<CreatorDetail | null>(null);
  const [stats, setStats] = useState<StatsSummary | null>(null);
  const [allVideos, setAllVideos] = useState<VideoSummary[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(() => uidStr !== undefined);
  const [landingLoaded, setLandingLoaded] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [aiOpen, setAiOpen] = useState(false);
  const [appendOpen, setAppendOpen] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [note, setNote] = useState<NoteState | null>(null);
  // 被拉進版邊的那一項：統計欄的一格、記錄上的一天、一個時長區間或一個時段。
  // 版面上必須留下朱批，否則讀者無從知道這份批註是從哪裡拉出來的。
  const [selected, setSelected] = useState<Selection>(null);
  const navigate = useNavigate();

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const fetchDetail = useCallback(
    async (id: number, refreshLibrary = true) => {
      try {
        const d = await api.getCreator(id);
        setDetail(d);
        const fetching =
          d.status === "pending" ||
          d.status === "fetching" ||
          d.refresh_status === "pending" ||
          d.refresh_status === "fetching";

        if (d.video_count > 0 && (refreshLibrary || !fetching)) {
          const [s, videos] = await Promise.all([
            api.getCreatorStatsSummary(id),
            fetchAllCreatorVideos(id),
          ]);
          setStats(s);
          setAllVideos(videos);
        }
        if (d.status === "error" && d.video_count === 0) {
          clearPoll();
          setErrorMsg(d.error_message ?? t("common.error"));
        }
      } catch {
        setErrorMsg(t("common.error"));
        clearPoll();
      }
    },
    [clearPoll, t],
  );

  useEffect(() => {
    if (!creatorId) return;
    // Fetching on mount and storing the result is what this effect is for; the
    // lint rule cannot see that every setState happens in an async callback.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDetail(creatorId).finally(() => setLoadingDetail(false));
    return clearPoll;
  }, [creatorId, fetchDetail, clearPoll, fetchStartedAt]);

  useEffect(() => {
    if (creatorId) return;
    let active = true;
    api
      .getCreators()
      .then((creators) => {
        if (active && creators[0]) {
          navigate(`/dashboard/${creators[0].uid}`, { replace: true });
        }
      })
      .finally(() => {
        if (active) setLandingLoaded(true);
      });
    return () => {
      active = false;
    };
  }, [creatorId, navigate]);

  useEffect(() => {
    if (!creatorId || !detail) return;
    if (
      detail.status === "pending" ||
      detail.status === "fetching" ||
      detail.refresh_status === "pending" ||
      detail.refresh_status === "fetching"
    ) {
      clearPoll();
      pollRef.current = setInterval(() => fetchDetail(creatorId, false), 3000);
    }
    return clearPoll;
  }, [detail, detail?.status, creatorId, fetchDetail, clearPoll]);

  const stages = useMemo<Stage[]>(() => {
    if (!detail) return [];
    const s = detail.status;
    const failed = s === "error";
    return [
      {
        key: "index",
        label: t("press.stage.index"),
        state: failed
          ? "error"
          : s === "pending" || s === "fetching"
            ? "running"
            : "done",
        detail: s === "pending" || s === "fetching" ? detail.progress : null,
      },
    ];
  }, [detail, t]);

  const mastheadMeta = useMemo(() => {
    if (!detail) return [];
    return [
      { label: "UID", value: String(detail.uid) },
      {
        label: t("masthead.span"),
        value: `${detail.start_date ?? "—"} — ${detail.end_date ?? "—"}`,
      },
      {
        label: t("stats.videos"),
        value: formatExact(detail.video_count, lang),
      },
      ...(detail.video_count > 0
        ? [{ label: t("stats.totalViews"), value: formatCount(detail.total_views, lang) }]
        : []),
    ];
  }, [detail, t, lang]);

  /** Everything the sheet aggregates can be pulled back apart into videos. */
  const openVideoNote = useCallback(
    (subject: string, meta: string | undefined, rows: VideoNoteRow[]) => {
      setNote({ subject, meta, rows, loading: false });
    },
    [],
  );

  const noteFromSet = useCallback(
    (
      subject: string,
      meta: string | undefined,
      pick: (v: VideoSummary) => boolean,
      mark: Selection = null,
    ) => {
      setSelected(mark);
      const rows = allVideos
        .filter(pick)
        .sort((a, b) => b.stats.views - a.stats.views)
        .slice(0, 20)
        .map((v) => ({ video: v, figure: formatCount(v.stats.views, lang) }));
      openVideoNote(subject, meta, rows);
    },
    [allVideos, lang, openVideoNote],
  );

  const handleLedgerClick = useCallback(
    async (row: LedgerRow) => {
      const metric = LEDGER_METRICS[row.key];
      if (!creatorId || !metric) return;
      setSelected({ kind: "ledger", key: row.key });
      setNote({ subject: row.label, meta: t("note.topTen"), rows: [], loading: true });
      try {
        const page = await api.getCreatorVideos(creatorId, {
          sort_by: metric.sortBy,
          order: "desc",
          page: "1",
          page_size: "10",
        });
        setNote({
          subject: row.label,
          meta: t("note.topTen"),
          loading: false,
          rows: page.items.map((v) => ({
            video: v,
            figure: metric.percent
              ? formatPercent(metric.value(v))
              : formatCount(metric.value(v), lang),
          })),
        });
      } catch {
        setNote({ subject: row.label, meta: t("common.error"), rows: [], loading: false });
      }
    },
    [creatorId, t, lang],
  );

  const handlePublishDayClick = useCallback(
    (day: PublishCalendarDay) => {
      setSelected({ kind: "date", key: day.date });
      openVideoNote(
        day.date,
        t("chart.publishDay", {
          date: day.date,
          count: day.count,
          maxViews: formatCount(day.maxViews, lang),
        }),
        day.videos.map((video) => ({
          video,
          figure: formatCount(video.stats.views, lang),
        })),
      );
    },
    [openVideoNote, t, lang],
  );

  const handleStatsRefresh = useCallback(async () => {
    if (!creatorId) return;
    setRefreshError(null);
    try {
      await api.refreshCreatorStats(creatorId);
      await fetchDetail(creatorId);
    } catch {
      setRefreshError(t("common.error"));
    }
  }, [creatorId, fetchDetail, t]);

  const ledgerRows = useMemo<LedgerRow[]>(() => {
    if (!stats) return [];
    const rows: [string, string, number][] = [
      ["views", t("stats.totalViews"), stats.total_views],
      ["likes", t("stats.likes"), stats.total_likes],
      ["coins", t("stats.coins"), stats.total_coins],
      ["favorites", t("stats.favorites"), stats.total_favorites],
      ["shares", t("stats.shares"), stats.total_shares],
      ["danmaku", t("stats.danmaku"), stats.total_danmaku],
      ["comments", t("stats.comments"), stats.total_comments],
      ["videos", t("stats.videos"), stats.video_count],
    ];
    return rows.map(([key, label, value]) => ({
      key,
      label,
      value: formatCount(value, lang),
      exact: formatExact(value, lang),
      open: selected?.kind === "ledger" && selected.key === key,
    }));
  }, [stats, t, lang, selected]);

  if (!creatorId) {
    if (!landingLoaded) {
      return <BlankSheet title={t("common.loading")} note={t("blank.loadingNote")} />;
    }
    return <BlankSheet title={t("blank.title")} note={t("blank.note")} />;
  }

  if (loadingDetail && !detail) {
    return <BlankSheet title={t("common.loading")} note={t("blank.loadingNote")} />;
  }

  const title = detail?.name || (detail ? `UID ${detail.uid}` : t("app.title"));

  if (errorMsg) {
    return (
      <>
        <Masthead title={title} meta={mastheadMeta} />
        <div className="flex flex-col gap-8 px-4 pt-6 pb-16 md:px-8">
          <div className="rule-double pt-5">
            <p className="font-song text-h3 font-semibold text-mark">{t("press.failedTitle")}</p>
            <p className="prose-cn mt-2 max-w-[46ch] text-body leading-[1.9] text-ink-2">
              {errorMsg}
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <Button variant="outline" onClick={() => fetchDetail(creatorId)}>
                {t("common.retry")}
              </Button>
            </div>
          </div>
          {/* 工序表：讀者要看得出是哪一道斷了，而不是只讀到「出錯了」。 */}
          {stages.length > 0 && (
            <div className="max-w-xl">
              <PressRun stages={stages} />
            </div>
          )}
        </div>
      </>
    );
  }

  if (
    detail &&
    detail.video_count === 0 &&
    (detail.status === "pending" || detail.status === "fetching")
  ) {
    return (
      <>
        <Masthead title={title} meta={mastheadMeta} />
        <div className="flex flex-col px-4 pt-6 pb-16 md:px-8">
          <div className="rule-double max-w-xl pt-5">
            <PressRun stages={stages} />
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Masthead
        title={title}
        meta={mastheadMeta}
        actions={
          detail ? (
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                onClick={handleStatsRefresh}
                disabled={
                  detail.refresh_status === "pending" ||
                  detail.refresh_status === "fetching" ||
                  detail.status === "pending" ||
                  detail.status === "fetching"
                }
              >
                {detail.refresh_status === "pending" ||
                detail.refresh_status === "fetching"
                  ? t("app.refreshingStats")
                  : t("app.refreshStats")}
              </Button>
              <Button variant="outline" onClick={() => setAppendOpen(true)}>
                {t("app.appendFetch")}
              </Button>
              <Button variant="default" onClick={() => setAiOpen(true)}>
                {t("ai.analyze")}
              </Button>
            </div>
          ) : undefined
        }
      />

      <div className="flex flex-col gap-10 px-4 pt-6 pb-16 md:px-8">
        {refreshError && (
          <p className="text-note text-mark">{refreshError}</p>
        )}
        {detail?.refresh_error && (
          <p className="text-note text-mark">{detail.refresh_error}</p>
        )}
        {detail?.error_message && detail.status === "done" && (
          <p className="text-note text-ink-3">
            {t("press.previousFetchFailed")}
          </p>
        )}
        {detail?.refresh_progress && (
          <p className="text-note text-pencil">{detail.refresh_progress}</p>
        )}
        {detail && (detail.status === "pending" || detail.status === "fetching") && (
          <div className="rule border-t border-rule-strong pt-3">
            <PressRun stages={stages} />
          </div>
        )}
        {/* 導言 + 播放量記錄 */}
        {detail && stats && (
          <InkIn className="grid items-start gap-x-10 gap-y-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
            {/* 兩欄共用同一條起始線：導言與記錄各自從欄標題下方起排。 */}
            <Column label={t("lede.label")}>
              <Lede detail={detail} stats={stats} videos={allVideos} />
            </Column>
            <Column label={t("chart.viewsTrend")}>
              <ViewsTrendChart
                creatorId={creatorId}
                height={186}
                selectedDate={selected?.kind === "date" ? selected.key : null}
                onPointClick={(date) =>
                  noteFromSet(
                    date,
                    t("note.publishedOn"),
                    (v) => Boolean(v.published_at?.startsWith(date)),
                    { kind: "date", key: date },
                  )
                }
              />
            </Column>
          </InkIn>
        )}

        {stats && (
          <InkIn delay={60}>
            <Ledger rows={ledgerRows} onFigureClick={handleLedgerClick} />
          </InkIn>
        )}

        {detail && <CreatorStatsPanel creator={detail} />}
        {detail && (
          <CreatorAccountGrowthCharts
            creatorId={creatorId}
            refreshKey={detail.last_stats_refresh_at}
          />
        )}

        {detail && detail.rankings.length > 0 && (
          <Section label={t("ranking.creatorSection")}>
            <Column label={t("ranking.current")}>
              <RankingHighlights
                items={detail.rankings}
                creatorId={creatorId}
              />
            </Column>
          </Section>
        )}

        <Section label={t("section.performance")}>
          <Columns className="lg:grid-cols-3">
            <Column label={t("chart.interaction")}>
              <InteractionChart creatorId={creatorId} />
            </Column>
            <Column label={t("chart.scatter")} action={<ScatterNote />}>
              <ScatterChart
                videos={allVideos}
                onVideoClick={(bvid) => navigate(`/video/${bvid}?uid=${creatorId}`)}
              />
            </Column>
            <Column label={t("chart.durationImpact")}>
              <DurationChart
                videos={allVideos}
                selectedBand={selected?.kind === "band" ? selected.key : null}
                onBandClick={(band) =>
                  noteFromSet(
                    band.label,
                    t("note.inBand"),
                    (v) => v.duration >= band.min && v.duration < band.max,
                    { kind: "band", key: band.label },
                  )
                }
              />
            </Column>
          </Columns>
          <div className="mt-8">
            <Column label={t("chart.publishCalendar")}>
              <PublishCalendar
                videos={allVideos}
                startDate={detail?.start_date ?? ""}
                endDate={detail?.end_date ?? ""}
                selectedDate={selected?.kind === "date" ? selected.key : null}
                onDayClick={handlePublishDayClick}
              />
            </Column>
          </div>
        </Section>

        <Section label={t("section.catalogue")}>
          <VideoList creatorId={creatorId} />
        </Section>

        <Colophon
          items={[
            detail ? `${t("colophon.fetches", { n: detail.query_count })}` : null,
            detail?.last_fetched_at
              ? `${t("colophon.fetched")} ${detail.last_fetched_at.slice(0, 19).replace("T", " ")}`
              : null,
          ]}
        />
      </div>

      <VideoNote
        open={note !== null}
        onOpenChange={(next) => {
          if (next) return;
          setNote(null);
          setSelected(null);
        }}
        subject={note?.subject ?? ""}
        meta={note?.meta}
        rows={note?.rows ?? []}
        loading={note?.loading ?? false}
        creatorId={creatorId}
      />

      <AIPanel uid={creatorId} open={aiOpen} onOpenChange={setAiOpen} />
      <NewQueryDialog
        open={appendOpen}
        onOpenChange={setAppendOpen}
        defaultUid={String(creatorId)}
      />
    </>
  );
}

function ScatterNote() {
  const { t } = useTranslation();
  return <span className="text-colophon text-ink-3">{t("chart.scatterFormula")}</span>;
}
