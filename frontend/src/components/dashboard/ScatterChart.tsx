import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { chartBase, valueAxis, useChartTokens, NAME_SIZE } from "@/lib/chart-theme";
import { GAP, formatExact, formatPercent } from "@/lib/format";
import { autoScaleRange, scaledDecimal, scaledNumber } from "@/lib/chart-scale";
import { NoInk } from "@/components/proof/States";
import type { VideoSummary } from "@/types";

/**
 * 播放量 vs 互動率 —— the blue-pencil line is the system's own note: the mean
 * interaction rate, so every dot reads as above or below it at a glance.
 */
export default function ScatterChart({
  videos,
  height = 236,
  onVideoClick,
}: {
  videos: VideoSummary[];
  height?: number;
  onVideoClick?: (bvid: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const k = useChartTokens();

  const meanRate = useMemo(() => {
    if (!videos.length) return null;
    return videos.reduce((s, v) => s + v.stats.interaction_rate, 0) / videos.length;
  }, [videos]);

  const option = useMemo(
    () => {
      const viewsRange = autoScaleRange(
        videos.map((video) => video.stats.views),
      );
      const rateRange = autoScaleRange(
        videos.map((video) => video.stats.interaction_rate),
      );
      const viewsSpan = viewsRange.max - viewsRange.min;
      const rateSpan = rateRange.max - rateRange.min;
      return {
        ...chartBase(k),
        tooltip: {
          ...chartBase(k).tooltip,
          trigger: "item",
          confine: true,
          formatter: (p: { data: { name: string; value: number[] } }) =>
            `${p.data.name}<br/>${t("stats.totalViews")}${GAP}${formatExact(p.data.value[0], i18n.language)}` +
            `<br/>${t("stats.interactionRate")}${GAP}${formatPercent(p.data.value[1])}`,
        },
        grid: { left: 4, right: 14, top: 18, bottom: 22, containLabel: true },
        xAxis: valueAxis(k, {
          name: t("stats.totalViews"),
          nameLocation: "middle",
          nameGap: 26,
          min: viewsRange.min,
          max: viewsRange.max,
          axisLabel: {
            color: k.ink3,
            fontSize: 10,
            fontFamily: k.font,
            formatter: (value: number) => scaledNumber(value, viewsSpan),
          },
          nameTextStyle: { color: k.ink3, fontSize: NAME_SIZE, fontFamily: k.font },
          splitLine: { show: false },
        }),
        yAxis: valueAxis(k, {
          min: rateRange.min,
          max: rateRange.max,
          axisLabel: {
            color: k.ink3,
            fontSize: 10,
            fontFamily: k.font,
            formatter: (value: number) =>
              `${scaledDecimal(value, rateSpan)}%`,
          },
        }),
        series: [
          {
            type: "scatter",
            data: videos.map((v) => ({
              value: [v.stats.views, v.stats.interaction_rate],
              name: v.title,
              bvid: v.bvid,
            })),
            symbolSize: 7,
            itemStyle: { color: k.ink, opacity: 0.6 },
            emphasis: { itemStyle: { color: k.mark, opacity: 1 } },
            markLine:
              meanRate !== null
                ? {
                    silent: true,
                    symbol: "none",
                    lineStyle: { color: k.pencil, width: 1, type: "dashed" },
                    label: {
                      formatter: `${t("stats.avgInteraction")} ${formatPercent(meanRate, 2)}`,
                      color: k.pencil,
                      fontSize: 10,
                      fontFamily: k.font,
                      position: "insideEndTop",
                    },
                    data: [{ yAxis: meanRate }],
                  }
                : undefined,
          },
        ],
      };
    },
    [videos, meanRate, k, t, i18n.language],
  );

  if (!videos.length) return <NoInk className="py-16" />;

  return (
    <div className={onVideoClick ? "cursor-pointer" : undefined}>
      <ReactECharts
        option={option}
        style={{ height }}
        notMerge
        lazyUpdate
        onEvents={
          onVideoClick
            ? {
                click: (params: { data?: { bvid?: string } }) => {
                  if (params.data?.bvid) onVideoClick(params.data.bvid);
                },
              }
            : undefined
        }
      />
    </div>
  );
}
