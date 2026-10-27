import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { SettingsIcon, SunIcon, MoonIcon, LaptopIcon } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { useTheme } from "@/hooks/useTheme";
import { CircleMark, DeleteMark } from "@/components/proof/marks";
import type { CreatorSummary } from "@/types";
import NewQueryDialog from "@/components/dashboard/NewQueryDialog";

interface SidebarProps {
  onNavigate?: () => void;
}

const THEME_ORDER = ["light", "dark", "system"] as const;

export default function Sidebar({ onNavigate }: SidebarProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { uid: activeUid } = useParams<{ uid?: string }>();
  const { theme, setTheme } = useTheme();

  const [creators, setCreators] = useState<CreatorSummary[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<CreatorSummary | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchCreators() {
      try {
        const data = await api.getCreators();
        if (active) setCreators(data);
      } catch {
        // The index keeps its last good state; the sheet says nothing it cannot prove.
      } finally {
        if (active) setLoaded(true);
      }
    }

    fetchCreators();
    const id = setInterval(fetchCreators, 3000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  function toggleLanguage() {
    const next = i18n.language.startsWith("zh") ? "en" : "zh";
    i18n.changeLanguage(next);
    localStorage.setItem("lang", next);
  }

  function cycleTheme() {
    const i = THEME_ORDER.indexOf(theme as (typeof THEME_ORDER)[number]);
    setTheme(THEME_ORDER[(i + 1) % THEME_ORDER.length]);
  }

  function go(to: string) {
    navigate(to);
    onNavigate?.();
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    const deletedUid = deleteTarget.uid;
    setDeleteError(null);
    try {
      await api.deleteCreator(deletedUid);
      setCreators((prev) => prev.filter((creator) => creator.uid !== deletedUid));
      if (activeUid === String(deletedUid)) navigate("/dashboard");
      setDeleteTarget(null);
    } catch {
      setDeleteError(t("sidebar.deleteFailed"));
    }
  }

  const ThemeIcon = theme === "dark" ? MoonIcon : theme === "light" ? SunIcon : LaptopIcon;

  return (
    <>
      <aside className="flex h-full flex-col bg-paper-2">
        {/* 刊頭 —— 與報頭同高（--head-h），兩條頭線接成橫貫整張紙的一條。 */}
        <div className="flex h-[var(--head-h)] shrink-0 flex-col justify-center border-b-2 border-rule-strong px-4">
          <p className="font-song text-h3 leading-none font-semibold tracking-tight text-ink">
            {t("app.title")}
          </p>
          <p className="colophon mt-1.5">{t("app.tagline")}</p>
        </div>

        <div className="px-4 py-3">
          <Button variant="default" size="lg" className="w-full" onClick={() => setDialogOpen(true)}>
            {t("app.addCreator")}
          </Button>
        </div>

        {/* 稿件目錄 */}
        <div className="flex min-h-0 flex-1 flex-col">
          <p className="column-label px-4 pb-1.5">{t("sidebar.creatorIndex")}</p>

          <ScrollArea className="min-h-0 flex-1">
            <ul className="border-t border-rule">
              {loaded && creators.length === 0 && (
                <li className="px-4 py-4 text-note leading-relaxed text-ink-3">
                  {t("sidebar.emptyIndex")}
                </li>
              )}
              {creators.map((creator) => {
                const isActive = activeUid === String(creator.uid);
                const busy =
                  creator.status === "pending" || creator.status === "fetching";
                return (
                  <li
                    key={creator.uid}
                    className={cn(
                      "group relative border-b border-rule transition-colors",
                      isActive ? "bg-paper" : "hover:bg-paper-2",
                    )}
                  >
                    {isActive && (
                      <CircleMark className="pointer-events-none absolute top-3 left-1.5 size-3.5 text-mark" />
                    )}
                    <button
                      type="button"
                      onClick={() => go(`/dashboard/${creator.uid}`)}
                      className="w-full py-2.5 pr-8 pl-6 text-left outline-none focus-visible:bg-paper-2"
                      aria-current={isActive ? "true" : undefined}
                    >
                      <p
                        className={cn(
                          "truncate font-song text-ui leading-snug font-semibold",
                          isActive ? "text-mark" : "text-ink",
                        )}
                      >
                        {creator.name || `UID ${creator.uid}`}
                      </p>
                      <p className="mt-0.5 truncate text-note tabular-nums text-ink-3">
                        {creator.start_date ?? "—"} — {creator.end_date ?? "—"}
                      </p>
                      <p className="text-note tabular-nums text-ink-3">
                        {t("sidebar.summary", {
                          videos: creator.video_count,
                          views: formatCount(creator.total_views, i18n.language),
                        })}
                      </p>
                      {creator.status !== "done" && (
                        <p
                          className={cn(
                            "mt-1 truncate text-note",
                            busy ? "text-pencil" : "text-mark",
                          )}
                        >
                          {busy
                            ? (creator.progress ?? t("press.running"))
                            : t(`press.status.${creator.status}`, {
                                defaultValue: creator.status,
                              })}
                        </p>
                      )}
                    </button>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(creator);
                      }}
                      className="absolute top-2.5 right-2 p-1 text-ink-3 opacity-0 transition-opacity hover:text-mark focus-visible:opacity-100 group-hover:opacity-100"
                      aria-label={t("sidebar.deleteCreator")}
                    >
                      <DeleteMark className="size-4" />
                    </button>
                  </li>
                );
              })}
            </ul>
          </ScrollArea>
        </div>

        {/* 版邊控制 */}
        <div className="flex items-center gap-1 border-t border-rule-strong px-3 py-2">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => go("/settings")}
            aria-label={t("settings.title")}
          >
            <SettingsIcon />
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={cycleTheme}
            aria-label={t(`theme.${theme}`)}
            title={t(`theme.${theme}`)}
          >
            <ThemeIcon />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto tracking-[0.14em]"
            onClick={toggleLanguage}
          >
            {i18n.language.startsWith("zh") ? "EN" : "中"}
          </Button>
        </div>
      </aside>

      <NewQueryDialog open={dialogOpen} onOpenChange={setDialogOpen} />

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteError(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("sidebar.deleteConfirmTitle")}</DialogTitle>
            <DialogDescription>
              {t("sidebar.deleteConfirmDesc", {
                name: deleteTarget?.name || `UID ${deleteTarget?.uid}`,
              })}
            </DialogDescription>
            {deleteError && (
              <p className="text-note text-mark">{deleteError}</p>
            )}
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteTarget(null);
                setDeleteError(null);
              }}
            >
              {t("common.cancel")}
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              {t("sidebar.deleteCreator")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
