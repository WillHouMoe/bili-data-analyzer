import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { chartBase, useChartTokens, NAME_SIZE } from "@/lib/chart-theme";
import { formatRadarTooltip } from "@/lib/radar-tooltip";
import { NoInk } from "@/components/proof/States";
import type { VideoComparison } from "@/types";

function radarTooltipPosition(
  _point: unknown,
  _params: unknown,
  _dom: HTMLElement,
  _rect: unknown,
  size: { contentSize: [number, number]; viewSize: [number, number] },
): [number, number] {
  return [Math.max(8, size.viewSize[0] - size.contentSize[0] - 8), 8];
}

/**
 * 本篇 vs 同期中线 —— each radius is a percentile within the creator's local
 * cohort, so the outline answers “how does this video rank?” rather than
 * comparing raw counts with different units.
 */
export default function RadarChart({
  data,
  height = 280,
}: {
  data: VideoComparison | null;
  height?: number;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const k = useChartTokens();

  const labels = useMemo(
    () => [
      t("stats.totalViews"),
      t("stats.likes"),
      t("stats.coins"),
      t("stats.favorites"),
      t("stats.shares"),
      t("stats.danmaku"),
      t("stats.comments"),
    ],
    [t],
  );

  const option = useMemo(() => {
    if (!data) return null;
    const tooltipHtml = formatRadarTooltip(
      labels,
      [
        {
          label: t("video.thisVideo"),
          color: k.mark,
          values: data.video_values,
        },
        {
          label: t("video.baseline"),
          color: k.ink2,
          values: data.baseline_values,
        },
      ],
      lang,
      { label: t("video.percentile"), values: data.percentile_ranks },
    );
    const reference = data.metrics.map(() => 50);

    return {
      ...chartBase(k),
      tooltip: {
        ...chartBase(k).tooltip,
        trigger: "item",
        confine: true,
        transitionDuration: 0,
        position: radarTooltipPosition,
        formatter: () => tooltipHtml,
      },
      legend: {
        data: [t("video.thisVideo"), t("video.baseline")],
        textStyle: { color: k.ink3, fontSize: NAME_SIZE, fontFamily: k.font },
        icon: "rect",
        itemWidth: 9,
        itemHeight: 9,
        bottom: 0,
      },
      radar: {
        indicator: labels.map((name, index) => ({
          name: `${name}\nP${Math.round(data.percentile_ranks[index])}`,
          max: 100,
        })),
        radius: "62%",
        center: ["50%", "46%"],
        splitNumber: 4,
        shape: "polygon",
        axisName: {
          color: k.ink3,
          fontSize: NAME_SIZE,
          fontFamily: k.font,
          lineHeight: NAME_SIZE + 3,
        },
        splitLine: { lineStyle: { color: k.rule } },
        splitArea: { show: false },
        axisLine: { lineStyle: { color: k.rule } },
      },
      series: [
        {
          type: "radar",
          symbolSize: 4,
          data: [
            {
              value: data.percentile_ranks,
              name: t("video.thisVideo"),
              areaStyle: { color: k.mark, opacity: 0.16 },
              lineStyle: { color: k.mark, width: 1.5 },
              itemStyle: { color: k.mark },
            },
            {
              value: reference,
              name: t("video.baseline"),
              areaStyle: { opacity: 0 },
              lineStyle: { color: k.ink2, width: 1, type: "dashed" },
              itemStyle: { color: k.ink2 },
            },
          ],
        },
      ],
    };
  }, [data, labels, k, lang, t]);

  if (!option) return <NoInk className="py-16" />;

  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />;
}
