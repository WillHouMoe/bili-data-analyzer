import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import {
  categoryAxis,
  chartBase,
  compactNumber,
  useChartTokens,
  valueAxis,
} from "@/lib/chart-theme";
import { formatExact } from "@/lib/format";
import { toTimedSeries } from "@/lib/time-series";
import { Inking, NoInk } from "@/components/proof/States";
import type { VideoGrowth } from "@/types";

export default function VideoGrowthChart({ bvid }: { bvid: string }) {
  const { t, i18n } = useTranslation();
  const k = useChartTokens();
  const [data, setData] = useState<VideoGrowth | null>(null);
  const [loadedBvid, setLoadedBvid] = useState("");

  useEffect(() => {
    let active = true;
    api
      .getVideoGrowth(bvid)
      .then((result) => {
        if (!active) return;
        setData(result);
        setLoadedBvid(bvid);
      })
      .catch(() => {
        if (!active) return;
        setData(null);
        setLoadedBvid(bvid);
      });
    return () => {
      active = false;
    };
  }, [bvid]);

  const points = useMemo(() => data?.points ?? [], [data]);
  const timeFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(i18n.language, {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Shanghai",
      }),
    [i18n.language],
  );

  const option = useMemo(
    () => ({
      ...chartBase(k),
      tooltip: {
        ...chartBase(k).tooltip,
        trigger: "axis",
        formatter: (params: { dataIndex: number }[]) => {
          const point = points[params[0]?.dataIndex ?? -1];
          if (!point) return "";
          return [
            timeFormatter.format(new Date(point.fetched_at)),
            `${t("stats.totalViews")} ${formatExact(point.views, i18n.language)}`,
            `${t("stats.likes")} ${formatExact(point.likes, i18n.language)}`,
            `${t("stats.interactionRate")} ${point.interaction_rate.toFixed(2)}%`,
          ].join("<br/>");
        },
      },
      grid: { left: 4, right: 16, top: 22, bottom: 6, containLabel: true },
      xAxis: {
        ...categoryAxis(k),
        type: "time",
        boundaryGap: false,
        axisLabel: {
          color: k.ink3,
          fontSize: 10,
          fontFamily: k.font,
          hideOverlap: true,
          formatter: (value: number) =>
            timeFormatter.format(new Date(value)),
        },
      },
      yAxis: valueAxis(k, {
        axisLabel: {
          color: k.ink3,
          fontSize: 10,
          fontFamily: k.font,
          formatter: (value: number) => compactNumber(value),
        },
      }),
      series: [
        {
          name: t("stats.totalViews"),
          type: "line",
          data: toTimedSeries(
            points,
            (point) => point.fetched_at,
            (point) => point.views,
          ),
          smooth: false,
          symbol: "circle",
          symbolSize: 5,
          lineStyle: { color: k.mark, width: 1.8 },
          itemStyle: { color: k.mark },
          areaStyle: { color: k.mark, opacity: 0.08 },
        },
      ],
    }),
    [points, k, t, i18n.language, timeFormatter],
  );

  if (loadedBvid !== bvid) return <Inking className="py-12" />;
  if (!points.length) return <NoInk className="py-12" />;

  return (
    <div>
      <p className="colophon pb-2">
        {t("chart.videoGrowthSummary", { n: points.length })}
      </p>
      <ReactECharts option={option} style={{ height: 220 }} notMerge lazyUpdate />
      {points.length === 1 && (
        <p className="pt-2 text-note leading-relaxed text-pencil">
          {t("chart.videoGrowthNeedsHistory")}
        </p>
      )}
    </div>
  );
}
