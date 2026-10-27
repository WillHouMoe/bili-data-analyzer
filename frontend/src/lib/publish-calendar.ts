import type { VideoSummary } from "@/types";

export type PublishCalendarLevel = 0 | 1 | 2 | 3 | 4;

export interface PublishCalendarDay {
  date: string;
  dayOfWeek: number;
  videos: VideoSummary[];
  count: number;
  /** Highest playback count among videos published that day. */
  maxViews: number;
  level: PublishCalendarLevel;
}

export interface PublishCalendarWeek {
  days: Array<PublishCalendarDay | null>;
  /** First month represented by this column, when the label should change. */
  monthLabel: string | null;
}

export interface PublishCalendar {
  weeks: PublishCalendarWeek[];
  totalDays: number;
  publishedCount: number;
}

function parseDateKey(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null;
  }
  return date;
}

function formatDateKey(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function publishLevel(maxViews: number, peakViews: number): PublishCalendarLevel {
  if (peakViews <= 0) return 1;
  return Math.max(1, Math.ceil((maxViews / peakViews) * 4)) as PublishCalendarLevel;
}

/**
 * Build a Sunday-first contribution calendar over the query's inclusive date
 * range. Video dates use the backend's stored calendar date so a square and
 * its detail list always agree.
 */
export function buildPublishCalendar(
  startDate: string,
  endDate: string,
  videos: VideoSummary[],
): PublishCalendar {
  const start = parseDateKey(startDate);
  const end = parseDateKey(endDate);
  if (!start || !end || start > end) {
    return { weeks: [], totalDays: 0, publishedCount: 0 };
  }

  const videosByDate = new Map<string, VideoSummary[]>();
  for (const video of videos) {
    if (!video.published_at) continue;
    const date = video.published_at.slice(0, 10);
    const parsed = parseDateKey(date);
    if (!parsed || parsed < start || parsed > end) continue;

    const sameDay = videosByDate.get(date) ?? [];
    sameDay.push(video);
    videosByDate.set(date, sameDay);
  }

  const days: PublishCalendarDay[] = [];
  for (const cursor = new Date(start); cursor <= end; cursor.setUTCDate(cursor.getUTCDate() + 1)) {
    const date = formatDateKey(cursor);
    const sameDay = videosByDate.get(date) ?? [];
    const maxViews = sameDay.reduce(
      (highest, video) => Math.max(highest, video.stats.views),
      0,
    );
    days.push({
      date,
      dayOfWeek: cursor.getUTCDay(),
      videos: sameDay,
      count: sameDay.length,
      maxViews,
      level: 0,
    });
  }
  const peakViews = days.reduce((highest, day) => Math.max(highest, day.maxViews), 0);
  for (const day of days) {
    day.level = day.count > 0 ? publishLevel(day.maxViews, peakViews) : 0;
  }

  const cells: Array<PublishCalendarDay | null> = [
    ...Array.from<null>({ length: start.getUTCDay() }).fill(null),
    ...days,
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const weeks: PublishCalendarWeek[] = [];
  let previousMonth: string | null = null;
  for (let index = 0; index < cells.length; index += 7) {
    const weekDays = cells.slice(index, index + 7);
    const firstDay = weekDays.find((day): day is PublishCalendarDay => day !== null);
    const month: string | null = firstDay?.date.slice(0, 7) ?? previousMonth;
    weeks.push({
      days: weekDays,
      monthLabel: month && month !== previousMonth ? month : null,
    });
    if (month) previousMonth = month;
  }

  return {
    weeks,
    totalDays: days.length,
    publishedCount: days.reduce((total, day) => total + day.count, 0),
  };
}
