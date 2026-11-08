import { describe, expect, it } from "vitest";
import { formatRadarTooltip } from "./radar-tooltip";

const labels = ["总播放量", "点赞", "投币", "收藏", "分享", "弹幕", "评论"];
const values = [8_813_435, 414_370, 204_423, 82_996, 48_406, 100_108, 48_372];
const baselineValues = [6_169_405, 290_059, 143_096, 58_097, 33_884, 70_076, 33_860];

describe("formatRadarTooltip", () => {
  it("shows exact series values and the cohort percentile", () => {
    const html = formatRadarTooltip(
      labels,
      [
        { label: "本篇", color: "#c23b23", values },
        {
          label: "同期中线",
          color: "#555555",
          values: baselineValues,
        },
      ],
      "zh-CN",
      { label: "同期分位", values: [72, 68, 64, 59, 55, 51, 49] },
    );

    expect(html).toContain("本篇");
    expect(html).toContain("同期中线");
    expect(html).toContain("同期分位");
    expect(html).toContain("总播放量");
    expect(html).toContain("8,813,435");
    expect(html).toContain("6,169,405");
    expect(html).toContain("P72");
    expect(html).toContain("P49");
  });

  it("uses the local number separator and escapes user-facing labels", () => {
    const html = formatRadarTooltip(
      ["<Views>"],
      [
        { label: "This <video>", color: "#c23b23", values: [6_532_141.5] },
        { label: "Average", color: "#555555", values: [6_532_141.5] },
      ],
      "en-US",
      { label: "Cohort percentile", values: [88] },
    );

    expect(html).toContain("This &lt;video&gt;");
    expect(html).toContain("&lt;Views&gt;");
    expect(html).toContain("Cohort percentile");
    expect(html).toContain("6,532,141.5");
    expect(html.match(/6,532,141\.5/g)).toHaveLength(2);
    expect(html).toContain("P88");
  });
});
