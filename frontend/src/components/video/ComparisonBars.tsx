import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";
import { NoInk } from "@/components/proof/States";
import type { VideoComparison } from "@/types";

const METRIC_KEYS: Record<string, string> = {
  views: "stats.totalViews",
  likes: "stats.likes",
  coins: "stats.coins",
  favorites: "stats.favorites",
  shares: "stats.shares",
  danmaku: "stats.danmaku",
  comments: "stats.comments",
};

/** Anything past ±200% is off the measure; the figure still prints exactly. */
const SCALE = 200;

/**
 * 增減欄 —— each metric read against the local cohort median, either side of a
 * centre rule. Above sits right in 朱批, below sits left in 藍鉛筆: direction is
 * position first and colour second, so it reads without either.
 */
export default function ComparisonBars({ data }: { data: VideoComparison | null }) {
  const { t } = useTranslation();

  if (!data || !data.metrics.length) return <NoInk className="py-16" />;

  return (
    <div className="flex flex-col">
      <p className="colophon pb-1">
        {t("video.baselineSummary", {
          count: data.baseline.sample_size,
          days: data.baseline.window_days,
        })}
      </p>
      <p className="colophon pb-2">{t("video.engagementTip")}</p>

      <ul className="border-t border-rule">
        {data.metrics.map((metric, i) => {
          const pct = data.percentage_diff[i];
          const unavailable = pct === null;
          const above = (pct ?? 0) >= 0;
          const width = unavailable ? 0 : Math.min(Math.abs(pct) / SCALE, 1) * 50;

          return (
            <li
              key={metric}
              className="grid grid-cols-[minmax(3.5rem,auto)_1fr_minmax(3.5rem,auto)] items-center gap-x-3 border-b border-rule py-1.5"
            >
              <span className="truncate text-note text-ink-2">
                {t(METRIC_KEYS[metric] ?? metric, { defaultValue: metric })}
              </span>

              <span className="relative flex h-2.5 items-stretch bg-paper-2" aria-hidden>
                {/* 中線：同期中位數就在這裡 */}
                <span className="absolute inset-y-[-3px] left-1/2 w-px -translate-x-1/2 bg-rule-2" />
                <span
                  className={cn("absolute inset-y-0", above ? "bg-pos" : "bg-neg")}
                  style={
                    above
                      ? { left: "50%", width: `${width}%` }
                      : { right: "50%", width: `${width}%` }
                  }
                />
              </span>

              <span
                className={cn(
                  "text-right text-note font-medium tabular-nums",
                  unavailable ? "text-ink-3" : above ? "text-pos" : "text-neg",
                )}
              >
                {unavailable ? (
                  "—"
                ) : (
                  <>
                    {above ? "+" : "−"}
                    {Math.abs(pct).toFixed(1)}%
                  </>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
