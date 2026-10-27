import { describe, expect, it } from "vitest";
import { formatRadarTooltip } from "./radar-tooltip";

const labels = ["总播放量", "点赞", "投币", "收藏", "分享", "弹幕", "评论"];
const values = [8_813_435, 414_370, 204_423, 82_996, 48_406, 100_108, 48_372];
const maxValues = [16_885_302, 1_045_849, 866_908, 345_919, 210_216, 445_234, 242_199];

describe("formatRadarTooltip", () => {
  it("shows exact source figures instead of normalised radar coordinates", () => {
    const normalisedViews = (values[0] / maxValues[0]) * 100;
    const html = formatRadarTooltip(
      { dataIndex: 0, marker: "<span></span>", name: "本篇", seriesName: "series0" },
      labels,
      values,
      "zh-CN",
    );

    expect(html).toContain("本篇");
    expect(html).not.toContain("series0");
    expect(html).toContain("总播放量");
    expect(html).toContain("8,813,435");
    expect(html).not.toContain(String(normalisedViews));
  });

  it("uses the local number separator for the average series", () => {
    const html = formatRadarTooltip(
      { dataIndex: 1, seriesName: "Average" },
      labels,
      [6_532_141.5],
      "en-US",
    );

    expect(html).toContain("Average");
    expect(html).toContain("6,532,141.5");
    expect(html).toContain("—");
  });
});
