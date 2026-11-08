import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { chartBase, categoryAxis, valueAxis, useChartTokens, NAME_SIZE } from "@/lib/chart-theme";
import { GAP, formatExact, formatPercent } from "@/lib/format";
import { autoScaleRange, scaledDecimal, scaledNumber } from "@/lib/chart-scale";
import { NoInk } from "@/components/proof/States";
import type { VideoSummary } from "@/types";

const RANGES = [
  { key: "0-1", min: 0, max: 60 },
  { key: "1-3", min: 60, max: 180 },
  { key: "3-5", min: 180, max: 300 },
  { key: "5-10", min: 300, max: 600 },
  { key: "10-20", min: 600, max: 1200 },
  { key: "20-30", min: 1200, max: 1800 },
  { key: "30+", min: 1800, max: Infinity },
];

/** 時長影響 —— average views as ink bars, interaction rate as the vermilion note. */
export default function DurationChart({
  videos,
  height = 236,
  onBandClick,
  selectedBand,
}: {
  videos: VideoSummary[];
  height?: number;
  onBandClick?: (band: { min: number; max: number; label: string }) => void;
  /** Label of the band whose note is open. */
  selectedBand?: string | null;
}) {
  const { t, i18n } = useTranslation();
  const k = useChartTokens();

  const rows = useMemo(
    () =>
      RANGES.map((range) => {
        const inRange = videos.filter((v) => v.duration >= range.min && v.duration < range.max);
        if (!inRange.length) return null;
        return {
          label: t(`chart.duration.${range.key}`),
          min: range.min,
          max: range.max,
          count: inRange.length,
          avgViews: Math.round(inRange.reduce((s, v) => s + v.stats.views, 0) / inRange.length),
          avgRate:
            inRange.reduce((s, v) => s + v.stats.interaction_rate, 0) / inRange.length,
        };
      }).filter((r): r is NonNullable<typeof r> => r !== null),
    [videos, t],
  );

  const option = useMemo(
    () => {
      const viewsRange = autoScaleRange(rows.map((row) => row.avgViews));
      const rateRange = autoScaleRange(rows.map((row) => row.avgRate));
      const viewsSpan = viewsRange.max - viewsRange.min;
      const rateSpan = rateRange.max - rateRange.min;
      return {
        ...chartBase(k),
        tooltip: {
          ...chartBase(k).tooltip,
          trigger: "axis",
          axisPointer: { type: "shadow", shadowStyle: { color: k.mark, opacity: 0.06 } },
          formatter: (params: { dataIndex: number }[]) => {
            const d = rows[params[0].dataIndex];
            if (!d) return "";
            return [
              `${d.label}`,
              `${t("stats.videoCount")}${GAP}${d.count}`,
              `${t("stats.avgViews")}${GAP}${formatExact(d.avgViews, i18n.language)}`,
              `${t("stats.avgInteraction")}${GAP}${formatPercent(d.avgRate)}`,
            ].join("<br/>");
          },
        },
        legend: {
          data: [t("stats.avgViews"), t("stats.avgInteraction")],
          textStyle: { color: k.ink3, fontSize: NAME_SIZE, fontFamily: k.font },
          icon: "rect",
          itemWidth: 9,
          itemHeight: 9,
          right: 0,
          top: 0,
        },
        grid: { left: 4, right: 4, top: 30, bottom: 4, containLabel: true },
        xAxis: categoryAxis(k, {
          data: rows.map((d) => d.label),
          axisLabel: { color: k.ink3, fontSize: 10, fontFamily: k.font, hideOverlap: true },
        }),
        yAxis: [
          valueAxis(k, {
            min: viewsRange.min,
            max: viewsRange.max,
            axisLabel: {
              color: k.ink3,
              fontSize: 10,
              fontFamily: k.font,
              formatter: (value: number) => scaledNumber(value, viewsSpan),
            },
          }),
          valueAxis(k, {
            position: "right",
            min: rateRange.min,
            max: rateRange.max,
            axisLabel: {
              color: k.ink3,
              fontSize: 10,
              fontFamily: k.font,
              formatter: (value: number) =>
                `${scaledDecimal(value, rateSpan)}%`,
            },
            splitLine: { show: false },
          }),
        ],
        series: [
          {
            name: t("stats.avgViews"),
            type: "bar",
            barMaxWidth: 34,
            data: rows.map((d) => d.avgViews),
            // 被拉進版邊的那一條上朱批，讀者才看得出批註從哪裡來。上色走回呼，
            // 資料維持純數字陣列，ECharts 就不必重置資料集。
            itemStyle: {
              color: (p: { dataIndex: number }) =>
                rows[p.dataIndex]?.label === selectedBand ? k.mark : k.seq[2],
            },
            emphasis: { itemStyle: { color: k.mark } },
            yAxisIndex: 0,
          },
          {
            name: t("stats.avgInteraction"),
            type: "line",
            data: rows.map((d) => Number(d.avgRate.toFixed(2))),
            lineStyle: { color: k.mark, width: 1.5 },
            itemStyle: { color: k.mark },
            symbol: "circle",
            symbolSize: 5,
            smooth: false,
            yAxisIndex: 1,
          },
        ],
      };
    },
    [rows, selectedBand, k, t, i18n.language],
  );

  if (!rows.length) return <NoInk className="py-16" />;

  return (
    <div className={onBandClick ? "cursor-pointer" : undefined}>
      <ReactECharts
        option={option}
        style={{ height }}
        // Merged, not rebuilt: marking a band re-renders while the cursor is
        // still over the bar, and a rebuilt chart leaves the element under the
        // pointer holding a series that no longer exists.
        lazyUpdate
        onEvents={
          onBandClick
            ? {
                click: (params: { dataIndex: number }) => {
                  const band = rows[params.dataIndex];
                  if (band) onBandClick({ min: band.min, max: band.max, label: band.label });
                },
              }
            : undefined
        }
      />
    </div>
  );
}
