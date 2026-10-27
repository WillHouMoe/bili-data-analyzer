import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { useTranslation } from "react-i18next";
import { api } from "@/lib/api";
import { chartBase, categoryAxis, valueAxis, useChartTokens } from "@/lib/chart-theme";
import { formatExact } from "@/lib/format";
import { Inking, NoInk } from "@/components/proof/States";
import type { InteractionData } from "@/types";

/**
 * 互動對比 —— four ordered actions, four steps of one ink ramp. They share a
 * unit and a scale, so hue would only add noise; pointing at one marks it.
 */
export default function InteractionChart({
  creatorId,
  height = 236,
}: {
  creatorId: number;
  height?: number;
}) {
  const { t, i18n } = useTranslation();
  const k = useChartTokens();
  const [data, setData] = useState<InteractionData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .getCreatorInteraction(creatorId)
      .then((d) => { if (active) setData(d); })
      .catch(() => { if (active) setData(null); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [creatorId]);

  const rows = useMemo(
    () =>
      data
        ? [
            { key: "likes", label: t("stats.likes"), value: data.likes },
            { key: "coins", label: t("stats.coins"), value: data.coins },
            { key: "favorites", label: t("stats.favorites"), value: data.favorites },
            { key: "shares", label: t("stats.shares"), value: data.shares },
          ]
        : [],
    [data, t],
  );

  const option = useMemo(
    () => ({
      ...chartBase(k),
      tooltip: {
        ...chartBase(k).tooltip,
        trigger: "axis",
        axisPointer: { type: "shadow", shadowStyle: { color: k.mark, opacity: 0.06 } },
        valueFormatter: (v: number) => formatExact(v, i18n.language),
      },
      grid: { left: 4, right: 12, top: 18, bottom: 4, containLabel: true },
      xAxis: categoryAxis(k, { data: rows.map((r) => r.label) }),
      yAxis: valueAxis(k),
      series: [
        {
          name: t("chart.interaction"),
          type: "bar",
          barMaxWidth: 44,
          data: rows.map((r, i) => ({ value: r.value, itemStyle: { color: k.seq[i] } })),
          emphasis: { itemStyle: { color: k.mark } },
        },
      ],
    }),
    [rows, k, t, i18n.language],
  );

  if (loading) return <Inking className="py-16" />;
  if (!data) return <NoInk className="py-16" />;

  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />;
}
