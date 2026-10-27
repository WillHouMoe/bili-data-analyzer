import { formatExact } from "./format";

export interface RadarTooltipParams {
  dataIndex?: number;
  marker?: string;
  name?: string;
  seriesName?: string;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/**
 * The radar coordinates are normalised to 0–100 for comparable shapes. Read
 * the unnormalised values back into the tooltip so users see the real counts.
 */
export function formatRadarTooltip(
  params: RadarTooltipParams,
  labels: string[],
  values: number[],
  lang: string,
): string {
  const title = escapeHtml(params.name ?? params.seriesName ?? "");
  const rows = labels.map((label, index) => {
    const value = formatExact(values[index], lang);
    return [
      '<div style="display:flex;align-items:center;gap:12px;line-height:1.7">',
      `<span style="width:10px">${params.marker ?? ""}</span>`,
      `<span style="flex:1">${escapeHtml(label)}</span>`,
      `<strong style="font-variant-numeric:tabular-nums">${value}</strong>`,
      "</div>",
    ].join("");
  });

  return [
    '<div style="min-width:180px">',
    `<div style="font-weight:600;padding-bottom:4px">${title}</div>`,
    ...rows,
    "</div>",
  ].join("");
}
