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

export interface PublishCalendarBusiestMonth {
  month: string;
  count: number;
}

export interface PublishCalendarSummary {
  publishedCount: number;
  activeDays: number;
  averagePerMonth: number;
  longestGapDays: number | null;
  busiestMonth: PublishCalendarBusiestMonth | null;
  topVideo: VideoSummary | null;
  topVideos: VideoSummary[];
  totalViews: number;
  throughDate: string;
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

function videosInRange(
  start: Date,
  end: Date,
  videos: VideoSummary[],
): Array<{ video: VideoSummary; date: string }> {
  const kept: Array<{ video: VideoSummary; date: string }> = [];
  for (const video of videos) {
    if (!video.published_at) continue;
    const date = video.published_at.slice(0, 10);
    const parsed = parseDateKey(date);
    if (!parsed || parsed < start || parsed > end) continue;
    kept.push({ video, date });
  }
  return kept;
}

/**
 * Years are offered only when the library spans more than one calendar year.
 * Years without uploads are omitted so selecting one never yields an empty wall.
 */
export function calendarYearOptions(
  startDate: string,
  endDate: string,
  videos: VideoSummary[],
): number[] {
  const start = parseDateKey(startDate);
  const end = parseDateKey(endDate);
  if (!start || !end || start > end) return [];

  const oneYearLater = new Date(start);
  oneYearLater.setUTCFullYear(start.getUTCFullYear() + 1);
  if (end <= oneYearLater) return [];

  const years = new Set<number>();
  for (const video of videos) {
    if (!video.published_at) continue;
    const date = video.published_at.slice(0, 10);
    const parsed = parseDateKey(date);
    if (!parsed || parsed < start || parsed > end) continue;
    years.add(parsed.getUTCFullYear());
  }
  return [...years].sort((a, b) => b - a);
}

export function buildPublishCalendarSummary(
  startDate: string,
  endDate: string,
  videos: VideoSummary[],
  today = new Date(),
): PublishCalendarSummary | null {
  const start = parseDateKey(startDate);
  const end = parseDateKey(endDate);
  if (!start || !end || start > end) return null;

  const selected = videosInRange(start, end, videos);
  const dates = [...new Set(selected.map(({ date }) => date))].sort();
  let longestGapDays: number | null = null;
  for (let index = 1; index < dates.length; index += 1) {
    const previous = Date.parse(`${dates[index - 1]}T00:00:00Z`);
    const current = Date.parse(`${dates[index]}T00:00:00Z`);
    const gap = Math.round((current - previous) / 86_400_000);
    longestGapDays = Math.max(longestGapDays ?? 0, gap);
  }

  const byMonth = new Map<string, number>();
  for (const { date } of selected) {
    const month = date.slice(0, 7);
    byMonth.set(month, (byMonth.get(month) ?? 0) + 1);
  }
  let busiestMonth: PublishCalendarBusiestMonth | null = null;
  for (const [month, count] of byMonth) {
    if (
      !busiestMonth ||
      count > busiestMonth.count ||
      (count === busiestMonth.count && month < busiestMonth.month)
    ) {
      busiestMonth = { month, count };
    }
  }

  const topVideos = selected
    .map(({ video }) => video)
    .sort((a, b) => b.stats.views - a.stats.views)
    .slice(0, 5);

  const todayUtc = new Date(
    Date.UTC(
      today.getUTCFullYear(),
      today.getUTCMonth(),
      today.getUTCDate(),
    ),
  );
  const through = end < todayUtc ? end : todayUtc > start ? todayUtc : start;
  const monthsCovered =
    (through.getUTCFullYear() - start.getUTCFullYear()) * 12 +
    through.getUTCMonth() -
    start.getUTCMonth() +
    1;

  return {
    publishedCount: selected.length,
    activeDays: dates.length,
    averagePerMonth:
      monthsCovered > 0 ? selected.length / monthsCovered : selected.length,
    longestGapDays,
    busiestMonth,
    topVideo: topVideos[0] ?? null,
    topVideos,
    totalViews: selected.reduce(
      (total, { video }) => total + video.stats.views,
      0,
    ),
    throughDate: formatDateKey(through),
  };
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
  for (const { video, date } of videosInRange(start, end, videos)) {
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
