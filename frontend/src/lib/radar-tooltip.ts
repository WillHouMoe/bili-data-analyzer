import { formatExact } from "./format";

export interface RadarTooltipSeries {
  label: string;
  color: string;
  values: number[];
}

export interface RadarTooltipPercentiles {
  label: string;
  values: number[];
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function marker(color: string): string {
  return [
    '<span aria-hidden="true" style="',
    "display:inline-block;width:8px;height:8px;margin-right:6px;",
    `background:${escapeHtml(color)};`,
    '"></span>',
  ].join("");
}

/**
 * The radar coordinates are normalised to 0–100 for comparable shapes. Read
 * both unnormalised series into one table so overlapping radar outlines cannot
 * make the tooltip switch between the two series while hovering. Percentile
 * ranks explain where the video sits even when the underlying counts have very
 * different scales.
 */
export function formatRadarTooltip(
  labels: string[],
  series: RadarTooltipSeries[],
  lang: string,
  percentiles?: RadarTooltipPercentiles,
): string {
  const rows = labels.map((label, index) => {
    return [
      `<span style="padding:2px 10px 2px 0">${escapeHtml(label)}</span>`,
      ...series.map(
        (item) =>
          `<strong style="padding:2px 0 2px 10px;text-align:right;font-variant-numeric:tabular-nums">${formatExact(item.values[index], lang)}</strong>`,
      ),
      ...(percentiles
        ? [
            `<strong style="padding:2px 0 2px 10px;text-align:right;font-variant-numeric:tabular-nums">P${Math.round(percentiles.values[index])}</strong>`,
          ]
        : []),
    ].join("");
  });
  const columnCount = series.length + (percentiles ? 1 : 0);

  return [
    '<div style="min-width:316px">',
    `<div style="display:grid;grid-template-columns:minmax(64px,1fr) repeat(${columnCount},minmax(72px,auto));column-gap:10px;align-items:center;line-height:1.65">`,
    "<span></span>",
    ...series.map(
      (item) =>
        `<span style="padding:2px 0 6px 10px;text-align:right;font-weight:600;white-space:nowrap">${marker(item.color)}${escapeHtml(item.label)}</span>`,
    ),
    ...(percentiles
      ? [
          `<span style="padding:2px 0 6px 10px;text-align:right;font-weight:600;white-space:nowrap">${escapeHtml(percentiles.label)}</span>`,
        ]
      : []),
    ...rows,
    "</div></div>",
  ].join("");
}
