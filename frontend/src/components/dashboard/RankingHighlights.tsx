import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { NoInk } from "@/components/proof/States";
import { Button } from "@/components/ui/button";
import {
  SiteAchievementIcon,
  WeeklyMustWatchIcon,
} from "@/components/dashboard/achievement-icons";
import type { RankingMatch } from "@/types";

interface AchievementRow {
  bvid: string;
  title: string;
  views: number;
  inLibrary: boolean;
  placements: RankingMatch[];
}

function groupByVideo(items: RankingMatch[]): AchievementRow[] {
  const grouped = new Map<string, AchievementRow>();
  for (const item of items) {
    const current = grouped.get(item.bvid);
    if (current) {
      current.placements.push(item);
      current.views = Math.max(current.views, item.views);
      current.inLibrary ||= item.in_library;
    } else {
      grouped.set(item.bvid, {
        bvid: item.bvid,
        title: item.title,
        views: item.views,
        inLibrary: item.in_library,
        placements: [item],
      });
    }
  }
  return [...grouped.values()];
}

function VideoLink({
  row,
  creatorId,
  showTitle,
}: {
  row: AchievementRow;
  creatorId?: number;
  showTitle: boolean;
}) {
  const className = `font-song text-ui font-semibold text-ink no-underline hover:text-mark ${
    showTitle ? "" : "line-clamp-1"
  }`;
  return row.inLibrary ? (
    <Link
      to={`/video/${row.bvid}${creatorId ? `?uid=${creatorId}` : ""}`}
      className={className}
    >
      {row.title}
    </Link>
  ) : (
    <a
      href={`https://www.bilibili.com/video/${row.bvid}`}
      target="_blank"
      rel="noopener noreferrer"
      className={className}
    >
      {row.title}
    </a>
  );
}

export default function RankingHighlights({
  items,
  creatorId,
  showTitle = true,
  collapsible = false,
}: {
  items: RankingMatch[];
  creatorId?: number;
  showTitle?: boolean;
  collapsible?: boolean;
}) {
  const { t } = useTranslation();
  const id = useId();
  const initialLimit = collapsible ? 5 : Number.MAX_SAFE_INTEGER;
  const [weeklyLimit, setWeeklyLimit] = useState(initialLimit);
  const [siteLimit, setSiteLimit] = useState(initialLimit);

  if (!items.length) {
    return <NoInk className="py-8" label={t("ranking.empty")} />;
  }

  const weeklyRows = groupByVideo(
    items.filter((item) => item.kind === "weekly"),
  )
    .map((row) => ({
      ...row,
      placements: [...row.placements].sort((a, b) => {
        const number = (period: string) =>
          Number(period.replace("weekly-", "")) || 0;
        return number(b.period) - number(a.period);
      }),
      latestIssue: Math.max(
        ...row.placements.map(
          (item) => Number(item.period.replace("weekly-", "")) || 0,
        ),
      ),
    }))
    .sort((a, b) => b.latestIssue - a.latestIssue);

  const siteRows = groupByVideo(
    items.filter((item) => item.kind !== "weekly"),
  )
    .map((row) => {
      const placements = [...row.placements].sort((a, b) => {
        if (a.kind === "highest" && b.kind !== "highest") return -1;
        if (b.kind === "highest" && a.kind !== "highest") return 1;
        return (a.rank ?? Number.MAX_SAFE_INTEGER) -
          (b.rank ?? Number.MAX_SAFE_INTEGER);
      });
      return {
        ...row,
        placements,
        highest: placements.find((item) => item.kind === "highest") ?? null,
        current: placements.find((item) => item.kind === "popular") ?? null,
      };
    })
    .sort((a, b) => {
      const rankA = a.highest?.rank ?? a.current?.rank ?? Number.MAX_SAFE_INTEGER;
      const rankB = b.highest?.rank ?? b.current?.rank ?? Number.MAX_SAFE_INTEGER;
      return rankA - rankB;
    });

  return (
    <div className="flex flex-col gap-6">
      {weeklyRows.length > 0 && (
        <section aria-labelledby={`${id}-weekly`}>
          <h4 id={`${id}-weekly`} className="column-label mb-2 font-sans">
            {t("ranking.kind.weekly")}
          </h4>
          <ul className="border-t border-rule-strong">
            {weeklyRows.slice(0, weeklyLimit).map((row) => (
              <li
                key={row.bvid}
                className="grid grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-3 border-b border-rule py-2.5"
              >
                <WeeklyMustWatchIcon className="size-5 text-[#ffb027]" />
                <div className="min-w-0">
                  <VideoLink
                    row={row}
                    creatorId={creatorId}
                    showTitle={showTitle}
                  />
                  <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-colophon text-ink-3">
                    {row.placements.map((placement) => (
                      <span key={placement.period}>
                        {placement.period_name ?? placement.period}
                      </span>
                    ))}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          {collapsible && weeklyRows.length > weeklyLimit && (
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() =>
                setWeeklyLimit((limit) =>
                  Math.min(weeklyRows.length, limit + 10),
                )
              }
            >
              {t("ranking.showMore", {
                count: Math.min(10, weeklyRows.length - weeklyLimit),
              })}
            </Button>
          )}
        </section>
      )}

      {siteRows.length > 0 && (
        <section aria-labelledby={`${id}-site`}>
          <h4 id={`${id}-site`} className="column-label mb-2 font-sans">
            {t("ranking.kind.popular")}
          </h4>
          <ul className="border-t border-rule-strong">
            {siteRows.slice(0, siteLimit).map((row) => (
              <li
                key={row.bvid}
                className="grid grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-3 border-b border-rule py-2.5"
              >
                <span className="flex items-center justify-start">
                  {row.highest ? (
                    <SiteAchievementIcon className="size-5 text-[#ff6699]" />
                  ) : (
                    <span className="text-right font-song text-h4 font-semibold tabular-nums text-mark">
                      {row.current?.rank === null ||
                      row.current?.rank === undefined
                        ? "—"
                        : `#${row.current.rank}`}
                    </span>
                  )}
                </span>
                <div className="min-w-0">
                  <VideoLink
                    row={row}
                    creatorId={creatorId}
                    showTitle={showTitle}
                  />
                  <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-colophon text-ink-3">
                    {row.highest && (
                      <span className="font-medium text-ink-2">
                        {row.highest.period_name ??
                          t("ranking.highestRank", {
                            rank: row.highest.rank,
                          })}
                      </span>
                    )}
                    {row.current?.rank !== null &&
                      row.current?.rank !== undefined && (
                        <span>
                          {t("ranking.currentRank", {
                            rank: row.current.rank,
                          })}
                        </span>
                      )}
                  </p>
                </div>
              </li>
            ))}
          </ul>
          {collapsible && siteRows.length > siteLimit && (
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() =>
                setSiteLimit((limit) =>
                  Math.min(siteRows.length, limit + 10),
                )
              }
            >
              {t("ranking.showMore", {
                count: Math.min(10, siteRows.length - siteLimit),
              })}
            </Button>
          )}
        </section>
      )}
    </div>
  );
}
