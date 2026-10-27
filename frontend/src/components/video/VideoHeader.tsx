import { useTranslation } from "react-i18next";
import { ExternalLinkIcon } from "lucide-react";
import { formatDuration } from "@/lib/format";
import type { VideoDetail } from "@/types";

/** 稿件頭：封面、提要、標籤 —— 一則稿子的來源說明。 */
export default function VideoHeader({ video }: { video: VideoDetail }) {
  const { t } = useTranslation();
  const tags = video.tags ? video.tags.split(",").map((s) => s.trim()).filter(Boolean) : [];

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:gap-6">
      <div className="relative shrink-0">
        {video.cover_url ? (
          <img
            src={video.cover_url}
            alt=""
            referrerPolicy="no-referrer"
            className="h-[125px] w-[200px] border border-rule object-cover"
          />
        ) : (
          <div className="flex h-[125px] w-[200px] items-center justify-center border border-dashed border-rule-2 text-note text-ink-3">
            {t("video.noCover")}
          </div>
        )}
        {video.duration > 0 && (
          <span className="absolute right-0 bottom-0 bg-ink px-1.5 py-0.5 text-note tabular-nums text-paper">
            {formatDuration(video.duration)}
          </span>
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-2.5">
        {video.description && (
          <p className="prose-cn line-clamp-4 text-note text-ink-2">{video.description}</p>
        )}

        {tags.length > 0 && (
          <p className="text-note leading-relaxed text-ink-3">
            <span className="column-label mr-2">{t("video.tags")}</span>
            {tags.join("、")}
          </p>
        )}

        <div className="mt-auto flex flex-wrap items-center gap-x-5 gap-y-2">
          <a
            href={`https://www.bilibili.com/video/${video.bvid}`}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-note text-ink-2 hover:text-mark"
          >
            {t("video.openOnBilibili")}
            <ExternalLinkIcon className="size-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
