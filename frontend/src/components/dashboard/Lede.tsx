import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Trans, useTranslation } from "react-i18next";
import { Emphasis } from "@/components/proof/Sheet";
import { formatCount, daysBetween } from "@/lib/format";
import type { CreatorDetail, StatsSummary, VideoSummary } from "@/types";

/**
 * 導言 —— one paragraph that stands on its own: the span, the video that broke
 * out (named, and linked to its own sheet), and what viewers did. Key figures
 * carry 著重號. Every number is computed from the fetched data, none asserted.
 */
export default function Lede({
  detail,
  stats,
  videos,
}: {
  detail: CreatorDetail;
  stats: StatsSummary;
  videos: VideoSummary[];
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  // 中文句子之間不留空格；英文才需要。
  const sep = lang.startsWith("zh") ? "" : " ";

  const facts = useMemo(() => {
    const count = stats.video_count;
    if (count <= 0) return null;

    const days =
      detail.start_date && detail.end_date
        ? daysBetween(detail.start_date, detail.end_date)
        : null;
    const avgViews = stats.total_views / count;
    const peak = videos.length
      ? videos.reduce((best, v) => (v.stats.views > best.stats.views ? v : best), videos[0])
      : null;
    const ratio = peak && avgViews > 0 ? peak.stats.views / avgViews : null;

    const actions = [
      { label: t("stats.likes"), value: stats.total_likes },
      { label: t("stats.coins"), value: stats.total_coins },
      { label: t("stats.favorites"), value: stats.total_favorites },
      { label: t("stats.shares"), value: stats.total_shares },
    ];
    const totalActions = actions.reduce((s, a) => s + a.value, 0);
    const topAction = [...actions].sort((a, b) => b.value - a.value)[0];
    const rate = stats.total_views > 0 ? (totalActions / stats.total_views) * 100 : null;

    return { count, days, peak, ratio, rate, topAction, totalActions };
  }, [detail, stats, videos, t]);

  if (!facts) return null;

  const breakout = facts.ratio !== null && facts.ratio >= 1.8;

  return (
    <p className="prose-cn text-h4 leading-[1.85] text-ink">
      {facts.days !== null && (
        <Trans
          i18nKey="lede.span"
          values={{
            days: facts.days,
            videos: facts.count,
            views: formatCount(stats.total_views, lang),
          }}
          components={{ e: <Emphasis /> }}
        />
      )}
      {sep}
      {facts.peak && facts.ratio !== null && (
        <Trans
          i18nKey={breakout ? "lede.peak" : "lede.even"}
          values={{
            title: facts.peak.title,
            peakViews: formatCount(facts.peak.stats.views, lang),
            ratio: facts.ratio.toFixed(1),
          }}
          components={{
            e: <Emphasis />,
            a: (
              <Link
                to={`/video/${facts.peak.bvid}?uid=${detail.uid}`}
                className="font-medium text-ink underline decoration-rule-2 hover:text-mark hover:decoration-mark"
              />
            ),
          }}
        />
      )}
      {sep}
      {facts.rate !== null && facts.totalActions > 0 && (
        <Trans
          i18nKey="lede.rate"
          values={{ rate: facts.rate.toFixed(2), action: facts.topAction.label }}
          components={{ e: <Emphasis /> }}
        />
      )}
    </p>
  );
}
