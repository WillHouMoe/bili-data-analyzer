import { useTranslation } from "react-i18next";
import { formatCount } from "@/lib/format";
import { Section } from "@/components/proof/Sheet";
import type { CreatorDetail } from "@/types";

export default function CreatorStatsPanel({
  creator,
}: {
  creator: CreatorDetail;
}) {
  const { t, i18n } = useTranslation();
  const metrics = [
    { key: "followers", label: t("stats.followers"), value: creator.followers },
    {
      key: "creatorViews",
      label: t("stats.creatorViews"),
      value: creator.creator_total_views,
    },
    {
      key: "creatorLikes",
      label: t("stats.creatorLikes"),
      value: creator.creator_total_likes,
    },
    {
      key: "archiveCount",
      label: t("stats.archiveCount"),
      value: creator.archive_count,
    },
    { key: "following", label: t("stats.following"), value: creator.following },
  ].filter(
    (metric): metric is typeof metric & { value: number } =>
      metric.value !== null,
  );

  if (!metrics.length) return null;

  const updated = creator.profile_stats_updated_at
    ? new Intl.DateTimeFormat(i18n.language, {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Shanghai",
      }).format(new Date(creator.profile_stats_updated_at))
    : null;

  return (
    <Section label={t("creatorStats.title")}>
      <dl className="grid grid-cols-2 border-y border-rule-strong sm:grid-cols-3 lg:grid-cols-5">
        {metrics.map((metric) => (
          <div
            key={metric.key}
            className="min-w-0 border-r border-b border-rule px-4 py-3 last:border-r-0 lg:border-b-0"
          >
            <dt className="column-label font-sans">{metric.label}</dt>
            <dd className="mt-1 font-sans text-h3 leading-none font-semibold tabular-nums text-ink">
              {formatCount(metric.value, i18n.language)}
            </dd>
          </div>
        ))}
      </dl>
      {updated && (
        <p className="mt-2 text-colophon text-ink-3">
          {t("creatorStats.updated", { time: updated })}
        </p>
      )}
    </Section>
  );
}
