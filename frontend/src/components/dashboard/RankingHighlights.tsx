import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { formatCount } from "@/lib/format";
import { NoInk } from "@/components/proof/States";
import type { RankingMatch } from "@/types";

export default function RankingHighlights({
  items,
  creatorId,
  showTitle = true,
}: {
  items: RankingMatch[];
  creatorId?: number;
  showTitle?: boolean;
}) {
  const { t, i18n } = useTranslation();

  if (!items.length) {
    return <NoInk className="py-8" label={t("ranking.empty")} />;
  }

  const grouped = new Map<
    string,
    {
      bvid: string;
      title: string;
      views: number;
      inLibrary: boolean;
      placements: RankingMatch[];
    }
  >();
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
  const rows = [...grouped.values()]
    .map((row) => ({
      ...row,
      placements: [...row.placements].sort((a, b) => a.rank - b.rank),
      bestRank: Math.min(...row.placements.map((item) => item.rank)),
    }))
    .sort((a, b) => a.bestRank - b.bestRank);

  return (
    <ul className="border-t border-rule-strong">
      {rows.map((row) => (
        <li
          key={row.bvid}
          className="grid grid-cols-[3rem_minmax(0,1fr)_auto] items-baseline gap-3 border-b border-rule py-2.5"
        >
          <span className="text-right font-song text-h4 font-semibold tabular-nums text-mark">
            #{row.bestRank}
          </span>
          <div className="min-w-0">
            {row.inLibrary ? (
              <Link
                to={`/video/${row.bvid}${creatorId ? `?uid=${creatorId}` : ""}`}
                className={`font-song text-ui font-semibold text-ink no-underline hover:text-mark ${
                  showTitle ? "" : "line-clamp-1"
                }`}
              >
                {row.title}
              </Link>
            ) : (
              <a
                href={`https://www.bilibili.com/video/${row.bvid}`}
                target="_blank"
                rel="noopener noreferrer"
                className={`font-song text-ui font-semibold text-ink no-underline hover:text-mark ${
                  showTitle ? "" : "line-clamp-1"
                }`}
              >
                {row.title}
              </a>
            )}
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-colophon text-ink-3">
              {row.placements.map((placement) => (
                <span key={`${placement.kind}:${placement.period}`}>
                  <span className="font-medium text-ink-2">
                    {t(`ranking.kind.${placement.kind}`)} #{placement.rank}
                  </span>
                  {placement.period_name ? ` · ${placement.period_name}` : ""}
                </span>
              ))}
            </p>
          </div>
          <span className="text-note tabular-nums text-ink-2">
            {formatCount(row.views, i18n.language)}
          </span>
        </li>
      ))}
    </ul>
  );
}
