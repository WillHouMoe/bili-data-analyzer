import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeftIcon } from "lucide-react";
import { api } from "@/lib/api";
import type { VideoDetail, VideoComparison } from "@/types";
import { formatCount, formatExact, formatDuration, formatPercent } from "@/lib/format";
import Masthead from "@/components/proof/Masthead";
import Ledger, { type LedgerRow } from "@/components/proof/Ledger";
import { Section, Column, Columns, Colophon, InkIn } from "@/components/proof/Sheet";
import { BlankSheet } from "@/components/proof/States";
import { Button } from "@/components/ui/button";
import VideoHeader from "@/components/video/VideoHeader";
import RadarChart from "@/components/video/RadarChart";
import ComparisonBars from "@/components/video/ComparisonBars";
import VideoGrowthChart from "@/components/video/VideoGrowthChart";
import RankingHighlights from "@/components/dashboard/RankingHighlights";

export default function VideoDetailPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { bvid } = useParams<{ bvid: string }>();
  const [searchParams] = useSearchParams();
  const creatorId = searchParams.get("uid") ? Number(searchParams.get("uid")) : null;

  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [comparison, setComparison] = useState<VideoComparison | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!bvid) return;

    const jobs: Promise<unknown>[] = [api.getVideo(bvid).then(setVideo)];

    if (creatorId) {
      // Comparison needs a creator library to compare against; its absence is
      // not an error.
      jobs.push(api.getCreatorComparison(creatorId, bvid).then(setComparison).catch(() => {}));
    }

    Promise.all(jobs)
      .catch(() => setError(t("common.error")))
      .finally(() => setLoading(false));
  }, [bvid, creatorId, t]);

  const backTo = creatorId ? `/dashboard/${creatorId}` : "/dashboard";

  const ledgerRows = useMemo<LedgerRow[]>(() => {
    if (!video) return [];
    const s = video.stats;
    const rows: [string, string, number][] = [
      ["views", t("stats.totalViews"), s.views],
      ["likes", t("stats.likes"), s.likes],
      ["coins", t("stats.coins"), s.coins],
      ["favorites", t("stats.favorites"), s.favorites],
      ["shares", t("stats.shares"), s.shares],
      ["danmaku", t("stats.danmaku"), s.danmaku_count],
      ["comments", t("stats.comments"), s.comment_count],
    ];
    return [
      ...rows.map(([key, label, value]) => ({
        key,
        label,
        value: formatCount(value, lang),
        exact: formatExact(value, lang),
      })),
      {
        key: "rate",
        label: t("stats.interactionRate"),
        value: formatPercent(s.interaction_rate),
        marked: true,
      },
    ];
  }, [video, t, lang]);

  if (loading) {
    return <BlankSheet title={t("common.loading")} note={t("blank.loadingNote")} />;
  }

  if (error || !video) {
    return (
      <BlankSheet
        title={t("common.error")}
        note={error ?? t("common.error")}
        action={
          <Link to={backTo}>
            <Button variant="outline" size="sm">
              {t("video.backToDashboard")}
            </Button>
          </Link>
        }
      />
    );
  }

  return (
    <>
      <Masthead
        title={video.title}
        back={
          <Link
            to={backTo}
            aria-label={t("video.backToDashboard")}
            className="inline-flex items-center gap-1 border-r border-rule pr-2.5 text-note text-ink-3 no-underline hover:text-mark sm:pr-3"
          >
            <ArrowLeftIcon className="size-3" />
            <span className="hidden sm:inline">{t("video.backToDashboard")}</span>
          </Link>
        }
        meta={[
          { label: "BV", value: video.bvid },
          ...(video.published_at
            ? [{ label: t("video.publishedAt"), value: video.published_at.slice(0, 10) }]
            : []),
          { label: t("video.duration"), value: formatDuration(video.duration) },
        ]}
      />

      <div className="flex flex-col gap-10 px-4 pt-6 pb-16 md:px-8">
        <InkIn>
          <VideoHeader video={video} />
        </InkIn>

        <InkIn delay={60}>
          <Ledger rows={ledgerRows} />
        </InkIn>

        <Section label={t("chart.videoGrowth")}>
          <Column label={t("chart.videoGrowthAxis")}>
            <VideoGrowthChart bvid={video.bvid} />
          </Column>
        </Section>

        {video.rankings.length > 0 && (
          <Section label={t("ranking.videoSection")}>
            <Column label={t("ranking.current")}>
              <RankingHighlights
                items={video.rankings}
                creatorId={creatorId ?? undefined}
                showTitle={false}
              />
            </Column>
          </Section>
        )}

        {comparison && (
          <Section label={t("video.comparison")}>
            <Columns className="lg:grid-cols-2">
              <Column label={t("video.shape")}>
                <RadarChart data={comparison} />
              </Column>
              <Column label={t("video.engagement")}>
                <ComparisonBars data={comparison} />
              </Column>
            </Columns>
          </Section>
        )}

        <Colophon
          items={[
            video.bvid,
            creatorId ? `${t("colophon.creator")} ${creatorId}` : null,
          ]}
        />
      </div>

    </>
  );
}
