import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MissingColumn } from "@/components/proof/States";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

interface NewQueryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultUid?: string;
}

type Preset = "7d" | "30d" | "3m" | "6m" | "1y" | "all";

const PRESETS: Preset[] = ["7d", "30d", "3m", "6m", "1y", "all"];

function presetDates(preset: Preset): { start: string; end: string } {
  const end = new Date();
  const start = new Date();
  const fmt = (d: Date) => d.toISOString().split("T")[0];

  switch (preset) {
    case "7d": start.setDate(end.getDate() - 7); break;
    case "30d": start.setDate(end.getDate() - 30); break;
    case "3m": start.setMonth(end.getMonth() - 3); break;
    case "6m": start.setMonth(end.getMonth() - 6); break;
    case "1y": start.setFullYear(end.getFullYear() - 1); break;
    case "all": start.setFullYear(2009, 5, 26); break; // Bilibili 建站
  }
  return { start: fmt(start), end: fmt(end) };
}

const dateFieldClass =
  "h-8 w-full border border-rule-2 bg-transparent px-2.5 py-1 font-sans text-ui tabular-nums text-ink outline-none transition-colors focus-visible:border-mark focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mark/40 max-sm:h-10";

/** 發稿單 —— what to fetch, over which span, and whether the press can read the text. */
export default function NewQueryDialog({
  open,
  onOpenChange,
  defaultUid,
}: NewQueryDialogProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [uid, setUid] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [activePreset, setActivePreset] = useState<Preset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sessdata, setSessdata] = useState<"checking" | "valid" | "invalid" | "missing" | null>(
    null,
  );

  useEffect(() => {
    if (!open) return;
    let ignore = false;

    (async () => {
      setSessdata("checking");
      try {
        const settings = await api.getSettings();
        if (ignore) return;
        if (!settings.sessdata) return setSessdata("missing");
        const test = await api.testSessdata(settings.sessdata);
        if (!ignore) setSessdata(test.status === "ok" ? "valid" : "invalid");
      } catch {
        if (!ignore) setSessdata("invalid");
      }
    })();

    return () => { ignore = true; };
  }, [open]);

  useEffect(() => {
    if (open && defaultUid) setUid(defaultUid);
  }, [open, defaultUid]);

  function reset() {
    setUid("");
    setStartDate("");
    setEndDate("");
    setActivePreset(null);
    setSessdata(null);
    setError(null);
  }

  function close(next: boolean) {
    onOpenChange(next);
    if (!next) reset();
  }

  function applyPreset(preset: Preset) {
    setActivePreset(preset);
    const { start, end } = presetDates(preset);
    setStartDate(start);
    setEndDate(end);
  }

  const rangeInvalid = Boolean(startDate && endDate && startDate > endDate);
  const canSubmit = Boolean(uid && startDate && endDate) && !rangeInvalid && !submitting;

  async function submit() {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.fetch(Number(uid), startDate, endDate);
      close(false);
      navigate(`/dashboard/${result.uid}`, {
        state: { fetchStartedAt: Date.now() },
      });
    } catch {
      setError(t("query.fetchFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {defaultUid ? t("query.appendTitle") : t("query.title")}
          </DialogTitle>
          <DialogDescription>
            {defaultUid ? t("query.appendSubtitle") : t("query.subtitle")}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          {sessdata === "missing" && (
            <MissingColumn
              title={t("query.sessdataMissingTitle")}
              note={t("query.sessdataWarning")}
              actionLabel={t("query.goToSettings")}
              actionTo="/settings"
            />
          )}
          {sessdata === "invalid" && (
            <MissingColumn
              title={t("query.sessdataInvalidTitle")}
              note={t("query.sessdataInvalid")}
              actionLabel={t("query.goToSettings")}
              actionTo="/settings"
            />
          )}

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="uid-input" className="column-label">{t("query.uid")}</Label>
            <Input
              id="uid-input"
              type="number"
              inputMode="numeric"
              placeholder="546195"
              value={uid}
              readOnly={Boolean(defaultUid)}
              onChange={(e) => setUid(e.target.value)}
            />
            <p className="text-colophon leading-relaxed tracking-normal text-ink-3">
              {t("query.uidHelp")}
            </p>
          </div>

          <div className="flex flex-col gap-2">
            <Label className="column-label">{t("query.dateRange")}</Label>
            <div className="flex flex-wrap gap-px border border-rule-2">
              {PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  aria-pressed={activePreset === preset}
                  className={cn(
                    "flex-1 px-2.5 py-1.5 text-note font-medium transition-colors outline-none",
                    "focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-mark",
                    activePreset === preset
                      ? "bg-ink text-paper"
                      : "bg-transparent text-ink-2 hover:bg-paper-3 hover:text-ink",
                  )}
                >
                  {t(`query.preset.${preset}`)}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="start-date" className="column-label">{t("query.startDate")}</Label>
                <input
                  id="start-date"
                  type="date"
                  value={startDate}
                  onChange={(e) => { setStartDate(e.target.value); setActivePreset(null); }}
                  className={dateFieldClass}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="end-date" className="column-label">{t("query.endDate")}</Label>
                <input
                  id="end-date"
                  type="date"
                  value={endDate}
                  onChange={(e) => { setEndDate(e.target.value); setActivePreset(null); }}
                  className={dateFieldClass}
                />
              </div>
            </div>

            {rangeInvalid && <p className="text-note text-mark">{t("query.rangeInvalid")}</p>}
          </div>

          {error && <p className="text-note text-mark">{error}</p>}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => close(false)} disabled={submitting}>
            {t("common.cancel")}
          </Button>
          <Button variant="default" onClick={submit} disabled={!canSubmit}>
            {submitting ? t("query.submitting") : t("common.fetchData")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
