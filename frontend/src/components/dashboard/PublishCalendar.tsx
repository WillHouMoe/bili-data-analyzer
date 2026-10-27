import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { NoInk } from "@/components/proof/States";
import { formatCount } from "@/lib/format";
import { buildPublishCalendar, type PublishCalendarDay } from "@/lib/publish-calendar";
import { cn } from "@/lib/utils";
import type { VideoSummary } from "@/types";

const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const;
const LEVEL_MIX = [0, 22, 40, 62, 86] as const;
const CELL = "size-3.5 rounded-[2px]";

function cellColor(level: PublishCalendarDay["level"]): string {
  if (level === 0) return "var(--paper-2)";
  return `color-mix(in oklab, var(--mark) ${LEVEL_MIX[level]}%, var(--paper-2))`;
}

/**
 * 發布日曆 —— a contribution wall over the query span. Every calendar day gets
 * a square; darker vermilion means its most-viewed upload performed better.
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

  const calendar = useMemo(
    () => buildPublishCalendar(startDate, endDate, videos),
    [startDate, endDate, videos],
  );

  const monthFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(i18n.language, {
        month: "short",
        timeZone: "UTC",
      }),
    [i18n.language],
  );

  if (!calendar.totalDays || calendar.publishedCount === 0) {
    return <NoInk className="py-16" />;
  }

  return (
    <div className="overflow-x-auto pb-1">
      <p className="colophon pb-3">{t("chart.publishCalendarHint")}</p>

      <div className="inline-flex min-w-max items-start gap-1.5">
        <div className="grid w-8 grid-rows-7 gap-[3px] pt-4">
          {WEEKDAY_KEYS.map((day, index) => (
            <span
              key={day}
              className="flex h-3.5 items-center text-[9px] leading-none text-ink-3"
            >
              {index === 1 || index === 3 || index === 5 ? t(`chart.day.${day}`) : null}
            </span>
          ))}
        </div>

        <div>
          <div
            className="grid h-4 gap-[3px] text-[9px] leading-none whitespace-nowrap text-ink-3"
            style={{ gridTemplateColumns: `repeat(${calendar.weeks.length}, 0.875rem)` }}
          >
            {calendar.weeks.map((week, index) => (
              <span key={week.monthLabel ?? `month-${index}`}>
                {week.monthLabel
                  ? monthFormatter.format(new Date(`${week.monthLabel}-01T00:00:00Z`))
                  : ""}
              </span>
            ))}
          </div>

          <div className="flex gap-[3px]">
            {calendar.weeks.map((week, weekIndex) => (
              <div key={`week-${weekIndex}`} className="grid grid-rows-7 gap-[3px]">
                {week.days.map((day, dayIndex) => {
                  if (!day) {
                    return <span key={`empty-${weekIndex}-${dayIndex}`} className={CELL} />;
                  }

                  const selected = selectedDate === day.date;
                  const style = { backgroundColor: cellColor(day.level) };
                  const title =
                    day.count > 0
                      ? t("chart.publishDay", {
                          date: day.date,
                          count: day.count,
                          maxViews: formatCount(day.maxViews, i18n.language),
                        })
                      : day.date;

                  return day.count > 0 && onDayClick ? (
                    <button
                      key={day.date}
                      type="button"
                      onClick={() => onDayClick(day)}
                      className={cn(
                        CELL,
                        "outline-none focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mark",
                        "hover:outline hover:outline-1 hover:outline-offset-1 hover:outline-mark",
                        selected && "outline-2 outline-offset-1 outline-mark",
                      )}
                      style={style}
                      title={title}
                      aria-label={title}
                      aria-pressed={selected}
                    />
                  ) : (
                    <span
                      key={day.date}
                      className={cn(CELL, selected && "outline-1 outline-offset-1 outline-mark")}
                      style={style}
                      title={title}
                    />
                  );
                })}
              </div>
            ))}
          </div>

          <div className="mt-3 flex items-center justify-end gap-2">
            <span className="colophon">{t("chart.publishViewsLow")}</span>
            <span className="flex gap-[3px]" aria-hidden>
              {LEVEL_MIX.map((_, level) => (
                <span
                  key={level}
                  className={CELL}
                  style={{ backgroundColor: cellColor(level as PublishCalendarDay["level"]) }}
                />
              ))}
            </span>
            <span className="colophon">{t("chart.publishViewsHigh")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
