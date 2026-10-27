import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Marginalia from "@/components/proof/Marginalia";
import { Inking, NoInk } from "@/components/proof/States";
import { formatCount, formatDuration } from "@/lib/format";
import type { VideoSummary } from "@/types";

export interface VideoNoteRow {
  video: VideoSummary;
  /** Already formatted; the figure this note is about, for this video. */
  figure: string;
}

/**
 * 影片旁批 —— the raw material behind an aggregate: which videos made it, and
 * how much each one contributed. Every ledger figure, trend point, duration
 * band and publish slot pulls into this note.
 */
export default function VideoNote({
  open,
  onOpenChange,
  subject,
  meta,
  rows,
  loading = false,
  creatorId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subject: string;
  meta?: string;
  rows: VideoNoteRow[];
  loading?: boolean;
  creatorId: number;
}) {
  const { t, i18n } = useTranslation();

  return (
    <Marginalia
      open={open}
      onOpenChange={onOpenChange}
      subject={subject}
      meta={meta}
    >
      {loading ? (
        <Inking />
      ) : rows.length === 0 ? (
        <NoInk />
      ) : (
        <ul className="border-t border-rule-strong">
          {rows.map(({ video, figure }, i) => (
            <li key={video.bvid} className="border-b border-rule py-2">
              <div className="flex items-baseline gap-2.5">
                <span className="w-5 shrink-0 text-right text-note tabular-nums text-ink-3">
                  {i + 1}
                </span>
                <Link
                  to={`/video/${video.bvid}?uid=${creatorId}`}
                  className="min-w-0 flex-1 font-song text-ui leading-snug font-semibold text-ink no-underline hover:text-mark"
                >
                  {video.title}
                </Link>
                <span className="shrink-0 text-ui tabular-nums text-ink">{figure}</span>
              </div>
              <p className="mt-0.5 pl-7 text-colophon text-ink-3">
                {video.published_at?.slice(0, 10)}
                {" · "}
                {formatDuration(video.duration)}
                {" · "}
                {formatCount(video.stats.views, i18n.language)} {t("video.viewsLabel")}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Marginalia>
  );
}
