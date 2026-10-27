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
import { Column, Section } from "@/components/proof/Sheet";
import { Inking, NoInk } from "@/components/proof/States";
import type { AccountGrowthPoint, CreatorAccountGrowth } from "@/types";

interface AccountSeries {
  id: string;
  label: string;
  color: string;
  value: (point: AccountGrowthPoint) => number | null;
  axisIndex?: 0 | 1;
}

function AccountChart({
  points,
  series,
  language,
}: {
  points: AccountGrowthPoint[];
  series: AccountSeries[];
  language: string;
}) {
  const k = useChartTokens();
  const formatter = useMemo(
    () =>
      new Intl.DateTimeFormat(language, {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Asia/Shanghai",
      }),
    [language],
  );
  const chartSeries = series.map((item) => ({
    ...item,
    data: toTimedSeries(
      points.filter((point) => item.value(point) !== null),
      (point) => point.fetched_at,
      (point) => item.value(point) as number,
    ),
  }));
  if (!chartSeries.some((item) => item.data.length)) {
    return <NoInk className="py-12" />;
  }
  const hasRightAxis = series.some((item) => item.axisIndex === 1);

  const option = {
    ...chartBase(k),
    tooltip: {
      ...chartBase(k).tooltip,
      trigger: "axis",
      formatter: (
        params: Array<{
          seriesName: string;
          value: [number, number];
        }>,
      ) => {
        const time = params[0]?.value?.[0];
        if (!time) return "";
        return [
          formatter.format(new Date(time)),
          ...params.map(
            (item) =>
              `${item.seriesName} ${formatExact(item.value[1], language)}`,
          ),
        ].join("<br/>");
      },
    },
    legend:
      series.length > 1
        ? {
            data: series.map((item) => item.label),
            right: 0,
            top: 0,
            itemWidth: 14,
            itemHeight: 2,
            textStyle: {
              color: k.ink3,
              fontSize: 10,
              fontFamily: k.font,
            },
          }
        : undefined,
    grid: {
      left: 4,
      right: hasRightAxis ? 36 : 14,
      top: series.length > 1 ? 30 : 18,
      bottom: 8,
      containLabel: true,
    },
    xAxis: {
      ...categoryAxis(k),
      type: "time",
      axisLabel: {
        color: k.ink3,
        fontSize: 10,
        fontFamily: k.font,
        hideOverlap: true,
        formatter: (time: number) => formatter.format(new Date(time)),
      },
    },
    yAxis: [
      valueAxis(k, {
        axisLabel: {
          color: k.ink3,
          fontSize: 10,
          fontFamily: k.font,
          formatter: (n: number) => compactNumber(n),
        },
      }),
      ...(hasRightAxis
        ? [
            valueAxis(k, {
              position: "right",
              splitLine: { show: false },
              axisLabel: {
                color: k.ink3,
                fontSize: 10,
                fontFamily: k.font,
                formatter: (n: number) => compactNumber(n),
              },
            }),
          ]
        : []),
    ],
    series: chartSeries.map((item) => ({
        name: item.label,
        type: "line",
        data: item.data,
        yAxisIndex: item.axisIndex ?? 0,
        symbol: "circle",
        symbolSize: 5,
        smooth: false,
        lineStyle: { color: item.color, width: 1.8 },
        itemStyle: { color: item.color },
        areaStyle:
          series.length === 1
            ? { color: item.color, opacity: 0.06 }
            : undefined,
      })),
  };

  return <ReactECharts option={option} style={{ height: 220 }} notMerge lazyUpdate />;
}

export default function CreatorAccountGrowthCharts({
  creatorId,
  refreshKey,
}: {
  creatorId: number;
  refreshKey?: string | null;
}) {
  const { t, i18n } = useTranslation();
  const k = useChartTokens();
  const requestKey = `${creatorId}:${refreshKey ?? ""}`;
  const [data, setData] = useState<CreatorAccountGrowth | null>(null);
  const [resolvedKey, setResolvedKey] = useState("");

  useEffect(() => {
    let active = true;
    api
      .getCreatorAccountGrowth(creatorId)
      .then((result) => {
        if (!active) return;
        setData(result);
        setResolvedKey(requestKey);
      })
      .catch(() => {
        if (!active) return;
        setData(null);
        setResolvedKey(requestKey);
      });
    return () => {
      active = false;
    };
  }, [creatorId, requestKey]);

  if (requestKey !== resolvedKey) return <Inking className="py-12" />;
  if (!data || !data.points.length) return <NoInk className="py-12" />;

  return (
    <Section label={t("accountGrowth.title")}>
      <p className="colophon pb-4">
        {t("accountGrowth.summary", { n: data.points.length })}
      </p>
      <div className="overflow-x-auto">
        <div className="grid min-w-[760px] grid-cols-2 gap-6">
          <Column label={t("accountGrowth.followers")}>
            <AccountChart
              points={data.points}
              series={[
                {
                  id: "followers",
                  label: t("accountGrowth.followers"),
                  color: k.pencil,
                  value: (point) => point.followers,
                },
              ]}
              language={i18n.language}
            />
          </Column>
          <Column label={t("accountGrowth.viewsAndLikes")}>
            <AccountChart
              points={data.points}
              series={[
                {
                  id: "views",
                  label: t("accountGrowth.views"),
                  color: k.mark,
                  value: (point) => point.total_views,
                },
                {
                  id: "likes",
                  label: t("accountGrowth.likes"),
                  color: k.seq[3],
                  value: (point) => point.total_likes,
                  axisIndex: 1,
                },
              ]}
              language={i18n.language}
            />
          </Column>
        </div>
      </div>
      {data.points.length === 1 && (
        <p className="mt-3 text-note leading-relaxed text-pencil">
          {t("accountGrowth.needsHistory")}
        </p>
      )}
    </Section>
  );
}
