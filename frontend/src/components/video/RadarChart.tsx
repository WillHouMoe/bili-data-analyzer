import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { chartBase, useChartTokens, NAME_SIZE } from "@/lib/chart-theme";
import { formatRadarTooltip } from "@/lib/radar-tooltip";
import { NoInk } from "@/components/proof/States";
import type { VideoComparison } from "@/types";

/**
 * 本篇 vs 平均 —— the video in vermilion over the run's average in ink outline.
 * Each axis is normalised against the run's own maximum, so the shape is
 * comparable across metrics with wildly different units.
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
    const norm = (values: number[]) =>
      values.map((v, i) => (v / Math.max(data.max_values[i], 1)) * 100);

    return {
      ...chartBase(k),
      tooltip: {
        ...chartBase(k).tooltip,
        trigger: "item",
        formatter: (params: {
          dataIndex?: number;
          marker?: string;
          name?: string;
          seriesName?: string;
        }) =>
          formatRadarTooltip(
            params,
            labels,
            params.dataIndex === 1 ? data.average_values : data.video_values,
            lang,
          ),
      },
      legend: {
        data: [t("video.thisVideo"), t("video.average")],
        textStyle: { color: k.ink3, fontSize: NAME_SIZE, fontFamily: k.font },
        icon: "rect",
        itemWidth: 9,
        itemHeight: 9,
        bottom: 0,
      },
      radar: {
        indicator: labels.map((name) => ({ name, max: 100 })),
        radius: "62%",
        center: ["50%", "46%"],
        splitNumber: 4,
        shape: "polygon",
        axisName: { color: k.ink3, fontSize: NAME_SIZE, fontFamily: k.font },
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
              value: norm(data.video_values),
              name: t("video.thisVideo"),
              areaStyle: { color: k.mark, opacity: 0.16 },
              lineStyle: { color: k.mark, width: 1.5 },
              itemStyle: { color: k.mark },
            },
            {
              value: norm(data.average_values),
              name: t("video.average"),
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
