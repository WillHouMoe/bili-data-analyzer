import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { NoInk } from "@/components/proof/States";
import { Figure } from "@/components/proof/Sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SEP, formatCount } from "@/lib/format";
import {
  buildPublishCalendar,
  buildPublishCalendarSummary,
  calendarYearOptions,
  type PublishCalendarDay,
} from "@/lib/publish-calendar";
import { cn } from "@/lib/utils";
import type { VideoSummary } from "@/types";

const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;
const LEVEL_MIX = [0, 22, 40, 62, 86] as const;
const CELL = "aspect-square w-full min-w-0 rounded-[2px]";
const SWATCH = "size-3 rounded-[2px]";

function cellColor(level: PublishCalendarDay["level"]): string {
  if (level === 0) return "var(--paper-2)";
  return `color-mix(in oklab, var(--mark) ${LEVEL_MIX[level]}%, var(--paper-2))`;
}

function formatAverage(value: number, lang: string): string {
  return new Intl.NumberFormat(lang, {
    maximumFractionDigits: 1,
  }).format(value);
}

/**
 * 发布日历 —— one selected year, followed by that year's top videos.
 * Darker vermilion means the day's most-viewed upload performed better.
 */
export default function PublishCalendar({
  videos,
  startDate,
  endDate,
  onDayClick,
  selectedDate,
}: {
  videos: VideoSummary[];
  startDate: string;
  endDate: string;
  onDayClick?: (day: PublishCalendarDay) => void;
  selectedDate?: string | null;
}) {
  const { t, i18n } = useTranslation();
  const years = useMemo(
    () => calendarYearOptions(startDate, endDate, videos),
    [startDate, endDate, videos],
  );
  const [requestedYear, setRequestedYear] = useState<number | null>(null);
  const [activeDay, setActiveDay] = useState<PublishCalendarDay | null>(null);
  const selectedYear =
    requestedYear !== null && years.includes(requestedYear)
      ? requestedYear
      : years[0] ?? null;

  const visibleStart = selectedYear ? `${selectedYear}-01-01` : startDate;
  const visibleEnd = selectedYear ? `${selectedYear}-12-31` : endDate;
  const calendar = useMemo(
    () => buildPublishCalendar(visibleStart, visibleEnd, videos),
    [visibleStart, visibleEnd, videos],
  );
  const summary = useMemo(
    () => buildPublishCalendarSummary(visibleStart, visibleEnd, videos),
    [visibleStart, visibleEnd, videos],
  );
  const monthSegments = useMemo(() => {
    const starts = calendar.weeks
      .map((week, index) =>
        week.monthLabel ? { month: week.monthLabel, start: index } : null,
      )
      .filter(
        (value): value is { month: string; start: number } => value !== null,
      );
    return starts.map((segment, index) => ({
      ...segment,
      weeks:
        (starts[index + 1]?.start ?? calendar.weeks.length) - segment.start,
    }));
  }, [calendar.weeks]);

  const monthFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(i18n.language, {
        month: "short",
        timeZone: "UTC",
      }),
    [i18n.language],
  );
  const busiestMonthFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(i18n.language, {
        year: "numeric",
        month: "long",
        timeZone: "UTC",
      }),
    [i18n.language],
  );
  const throughDateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(i18n.language, {
        year: "numeric",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      }),
    [i18n.language],
  );

  if (!calendar.totalDays || calendar.publishedCount === 0 || !summary) {
    return <NoInk className="py-16" />;
  }

  const busiestMonth = summary.busiestMonth
    ? {
        label: busiestMonthFormatter.format(
          new Date(`${summary.busiestMonth.month}-01T00:00:00Z`),
        ),
        count: summary.busiestMonth.count,
      }
    : null;
  const partialYear = summary.throughDate < visibleEnd;
  const rangeLabel = selectedYear
    ? t("chart.publishYearLabel", { year: selectedYear })
    : `${visibleStart} — ${visibleEnd}`;
  const activeTopVideo = activeDay?.videos.reduce(
    (best, video) =>
      best === null || video.stats.views > best.stats.views ? video : best,
    null as VideoSummary | null,
  );
  const activityReadout = activeDay
    ? t("chart.publishHover", {
        date: activeDay.date,
        count: activeDay.count,
        maxViews: formatCount(activeDay.maxViews, i18n.language),
        title: activeTopVideo?.title ?? "",
      })
    : t("chart.publishCalendarTotal", {
        count: summary.publishedCount,
      });

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-3 pb-3">
        <p className="colophon max-w-2xl">{t("chart.publishCalendarHint")}</p>
        {years.length > 0 && (
          <label className="flex items-center gap-2">
            <span className="column-label font-sans">{t("chart.publishYear")}</span>
            <Select
              value={String(selectedYear)}
              onValueChange={(value: string | null) => {
                if (value) {
                  setRequestedYear(Number(value));
                  setActiveDay(null);
                }
              }}
            >
              <SelectTrigger className="w-28" aria-label={t("chart.publishYear")}>
                <SelectValue>
                  {t("chart.publishYearValue", { year: selectedYear })}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {years.map((year) => (
                  <SelectItem key={year} value={String(year)}>
                    {t("chart.publishYearValue", { year })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
        )}
      </div>

      <div className="grid gap-x-8 gap-y-6 lg:grid-cols-[minmax(0,1fr)_16rem]">
        <div className="min-w-0">
          <div className="mb-3 flex min-w-[640px] items-center justify-between gap-4 pl-10">
            <p
              className="min-h-4 min-w-0 truncate text-note text-ink-2"
              aria-live="polite"
            >
              {activityReadout}
            </p>
            <div className="flex shrink-0 items-center gap-2">
              <span className="colophon">{t("chart.publishViewsLow")}</span>
              <span className="flex gap-[3px]" aria-hidden>
                {LEVEL_MIX.map((_, level) => (
                  <span
                    key={level}
                    className={SWATCH}
                    style={{
                      backgroundColor: cellColor(
                        level as PublishCalendarDay["level"],
                      ),
                    }}
                  />
                ))}
              </span>
              <span className="colophon">{t("chart.publishViewsHigh")}</span>
            </div>
          </div>

          <div className="overflow-x-auto pb-1">
            <div
              className="grid min-w-[640px] grid-cols-[2rem_minmax(0,1fr)] gap-x-2"
              aria-label={t("chart.publishCalendar")}
            >
              <div className="grid grid-rows-7 gap-[3px]">
                {WEEKDAY_KEYS.map((day, index) => (
                  <span
                    key={day}
                    className="flex items-center text-[9px] leading-none text-ink-3"
                  >
                    {index === 1 || index === 3 || index === 5
                      ? t(`chart.day.${day}`)
                      : null}
                  </span>
                ))}
              </div>

              <div
                className="grid grid-flow-col grid-rows-7 gap-[3px]"
                onMouseLeave={() => setActiveDay(null)}
                style={{
                  gridTemplateColumns: `repeat(${calendar.weeks.length}, minmax(0, 1fr))`,
                }}
              >
                {calendar.weeks.flatMap((week, weekIndex) =>
                  week.days.map((day, dayIndex) => {
                    const position = {
                      gridColumn: weekIndex + 1,
                      gridRow: dayIndex + 1,
                    };
                    if (!day) {
                      return (
                        <span
                          key={`empty-${weekIndex}-${dayIndex}`}
                          className={CELL}
                          style={position}
                        />
                      );
                    }

                    const selected = selectedDate === day.date;
                    const title =
                      day.count > 0
                        ? t("chart.publishHover", {
                            date: day.date,
                            count: day.count,
                            maxViews: formatCount(
                              day.maxViews,
                              i18n.language,
                            ),
                            title:
                              day.videos.reduce(
                                (best, video) =>
                                  video.stats.views > best.stats.views
                                    ? video
                                    : best,
                                day.videos[0],
                              )?.title ?? "",
                          })
                        : t("chart.publishHoverEmpty", { date: day.date });
                    const commonProps = {
                      style: {
                        ...position,
                        backgroundColor: cellColor(day.level),
                      },
                      title,
                      onMouseEnter: () => setActiveDay(day),
                    };

                    return day.count > 0 && onDayClick ? (
                      <button
                        key={day.date}
                        type="button"
                        onClick={() => onDayClick(day)}
                        onFocus={() => setActiveDay(day)}
                        onBlur={() => setActiveDay(null)}
                        className={cn(
                          CELL,
                          "outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mark",
                          "hover:outline hover:outline-1 hover:outline-offset-1 hover:outline-mark",
                          selected &&
                            "outline-2 outline-offset-1 outline-mark",
                        )}
                        aria-label={title}
                        aria-pressed={selected}
                        {...commonProps}
                      />
                    ) : (
                      <span
                        key={day.date}
                        className={cn(
                          CELL,
                          selected &&
                            "outline-1 outline-offset-1 outline-mark",
                        )}
                        {...commonProps}
                      />
                    );
                  }),
                )}
              </div>

              <span aria-hidden />
              <div
                className="mt-1 grid text-[9px] leading-none text-ink-3"
                style={{
                  gridTemplateColumns: `repeat(${calendar.weeks.length}, minmax(0, 1fr))`,
                }}
              >
                {monthSegments.map((segment) => (
                  <span
                    key={segment.month}
                    className="overflow-visible whitespace-nowrap"
                    style={{
                      gridColumn: `${segment.start + 1} / span ${segment.weeks}`,
                    }}
                  >
                    {monthFormatter.format(
                      new Date(`${segment.month}-01T00:00:00Z`),
                    )}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 border-t border-rule-strong pt-3">
            <h4 className="font-song text-ui font-semibold text-ink">
              {selectedYear
                ? t("chart.publishLeaderboard", { year: selectedYear })
                : t("chart.publishLeaderboardRange")}
            </h4>
            <ol className="mt-2 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
              {summary.topVideos.map((video, index) => (
                <li
                  key={video.bvid}
                  className="min-w-0 border-l border-rule pl-3"
                >
                  <span className="text-note font-medium text-mark tabular-nums">
                    {index + 1}
                  </span>
                  <p className="mt-1 line-clamp-2 font-song text-note leading-snug text-ink">
                    {video.title}
                  </p>
                  <p className="mt-1 text-colophon tabular-nums text-ink-3">
                    {formatCount(video.stats.views, i18n.language)}
                    {video.published_at && (
                      <>
                        {SEP}
                        {video.published_at.slice(0, 10)}
                      </>
                    )}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <aside className="flex flex-col gap-4 border-t border-rule pt-4 lg:border-t-0 lg:border-l lg:border-rule lg:pt-0 lg:pl-6">
          <div>
            <h3 className="font-song text-ui font-semibold text-ink">
              {t("chart.publishSummary")}
            </h3>
            <p className="mt-1 text-note text-ink-3">
              {rangeLabel}
              {partialYear &&
                ` ${SEP} ${t("chart.publishThrough", {
                  date: throughDateFormatter.format(
                    new Date(`${summary.throughDate}T00:00:00Z`),
                  ),
                })}`}
            </p>
          </div>

          <div className="flex items-baseline justify-between gap-3 border-y border-rule py-3">
            <span className="column-label font-sans">
              {t("chart.publishVideos")}
            </span>
            <strong className="text-h4 font-medium text-ink tabular-nums">
              {formatCount(summary.publishedCount, i18n.language)}
            </strong>
          </div>

          <dl className="flex flex-col gap-3">
            <div className="flex items-baseline justify-between gap-3">
              <dt className="column-label font-sans">
                {t("chart.publishMonthlyAverage")}
              </dt>
              <dd className="text-note tabular-nums text-ink">
                {formatAverage(summary.averagePerMonth, i18n.language)}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="column-label font-sans">
                {t("chart.publishLongestGap")}
              </dt>
              <dd className="text-note tabular-nums text-ink">
                {summary.longestGapDays === null
                  ? "—"
                  : t("chart.publishDays", { count: summary.longestGapDays })}
              </dd>
            </div>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="column-label font-sans">
                {t("chart.publishBusiestMonth")}
              </dt>
              <dd className="text-right text-note text-ink">
                {busiestMonth
                  ? `${busiestMonth.label}${SEP}${t("chart.publishVideosCount", {
                      count: busiestMonth.count,
                    })}`
                  : "—"}
              </dd>
            </div>
          </dl>

          <div className="mt-auto border-t border-rule pt-3">
            <Figure
              label={t("chart.publishTotalViews")}
              value={formatCount(summary.totalViews, i18n.language)}
            />
          </div>
        </aside>
      </div>
    </div>
  );
}
