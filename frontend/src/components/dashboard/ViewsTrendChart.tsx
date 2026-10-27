import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { chartBase, categoryAxis, useChartTokens, compactNumber } from "@/lib/chart-theme";
import { formatExact } from "@/lib/format";
import { Inking, NoInk } from "@/components/proof/States";
import type { TrendPoint } from "@/types";

/**
 * 播放量記錄 —— one continuous ink line, unsmoothed, with the peak circled in
 * vermilion. A record is drawn as it happened, not curved into a nicer shape.
 */
export default function ViewsTrendChart({
  creatorId,
  height = 236,
  onPointClick,
  selectedDate,
}: {
  creatorId: number;
  height?: number;
  onPointClick?: (date: string) => void;
  /** Date of the reading whose note is open. */
  selectedDate?: string | null;
}) {
  const { t, i18n } = useTranslation();
  const k = useChartTokens();
  const [data, setData] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .getCreatorTrend(creatorId)
      .then((d) => { if (active) setData(d); })
      .catch(() => { if (active) setData([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [creatorId]);

  const peak = useMemo(
    () => data.reduce((best, p, i) => (p.views > (data[best]?.views ?? -1) ? i : best), 0),
    [data],
  );

  const option = useMemo(() => {
    return {
      ...chartBase(k),
      tooltip: {
        ...chartBase(k).tooltip,
        trigger: "axis",
        valueFormatter: (v: number) => formatExact(v, i18n.language),
      },
      grid: { left: 32, right: 32, top: 30, bottom: 2, containLabel: true },
      xAxis: categoryAxis(k, {
        data: data.map((p) => p.date),
        boundaryGap: false,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: k.rule } },
      }),
      // No scale furniture: the line is the record, the ledger carries totals
      // and the peak prints its own figure.
      yAxis: { type: "value", show: true, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
      series: [
        {
          name: t("chart.viewsTrend"),
          type: "line",
          data: data.map((p) => p.views),
          smooth: false,
          // Every reading is a mark on the record, and a mark you can point at.
          symbol: "circle",
          showSymbol: data.length <= 120,
          // 被讀進版邊的那一天圈上朱批並放大；其餘照舊是墨點。
          symbolSize: (_v: unknown, p: { dataIndex: number }) =>
            data[p.dataIndex]?.date === selectedDate ? 9 : data.length <= 40 ? 4 : 3,
          // The line itself is the target: a long record draws no symbols, and a
          // reading you cannot click is not a reading you can pull into the margin.
          triggerLineEvent: true,
          lineStyle: { color: k.ink, width: 1.5 },
          itemStyle: {
            color: (p: { dataIndex: number }) =>
              data[p.dataIndex]?.date === selectedDate ? k.mark : k.ink,
          },
          emphasis: { itemStyle: { color: k.mark, borderColor: k.mark } },
          markPoint:
            data.length > 1
              ? {
                  symbol: "circle",
                  symbolSize: 9,
                  itemStyle: { color: "transparent", borderColor: k.mark, borderWidth: 1.5 },
                  label: {
                    show: true,
                    position: "top",
                    distance: 8,
                    color: k.mark,
                    fontSize: 11,
                    fontFamily: k.font,
                    formatter: () => `${t("chart.peak")} ${compactNumber(data[peak].views)}`,
                  },
                  data: [{ coord: [peak, data[peak].views], name: t("chart.peak") }],
                }
              : undefined,
        },
      ],
    };
  }, [data, peak, selectedDate, k, t, i18n.language]);

  if (loading) return <Inking className="py-16" />;
  if (!data.length) return <NoInk className="py-16" />;

  return (
    <div className={onPointClick ? "cursor-pointer" : undefined}>
      <ReactECharts
        option={option}
        style={{ height }}
        notMerge
        lazyUpdate
        onEvents={
          onPointClick
            ? {
                click: (params: { dataIndex: number; componentType?: string }) => {
                  // 峰值那個圈是 markPoint，自帶一組資料：它的 dataIndex 不是
                  // 折線上的序號，照收會把最高的一天讀成第一天。
                  const i = params.componentType === "markPoint" ? peak : params.dataIndex;
                  const point = data[i];
                  if (point) onPointClick(point.date);
                },
              }
            : undefined
        }
      />
    </div>
  );
}
