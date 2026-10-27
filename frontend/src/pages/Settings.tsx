import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { EyeIcon, EyeOffIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useTheme, type Theme } from "@/hooks/useTheme";
import i18n from "@/i18n";
import { cn } from "@/lib/utils";
import Masthead from "@/components/proof/Masthead";
import { InkPulse } from "@/components/proof/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogTrigger,
  DialogClose,
} from "@/components/ui/dialog";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { BlankSheet } from "@/components/proof/States";

type TestStatus = "idle" | "loading" | "ok" | "error";

const MASK = "***";

/** 規格表的一列：左欄是項目名，右欄是填寫區。 */
function SpecRow({
  label,
  help,
  children,
}: {
  label: string;
  help?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid gap-x-8 gap-y-2 border-b border-rule py-4 md:grid-cols-[minmax(8rem,1fr)_minmax(0,2.4fr)]">
      <div>
        <p className="font-song text-ui font-semibold text-ink">{label}</p>
        {help && <p className="mt-1 text-note leading-relaxed text-ink-3">{help}</p>}
      </div>
      <div className="flex flex-col gap-2.5">{children}</div>
    </div>
  );
}

function TestResult({ status, message }: { status: TestStatus; message: string }) {
  if (status !== "ok" && status !== "error") return null;
  return (
    <span
      className={cn("text-note leading-relaxed", status === "ok" ? "text-pencil" : "text-mark")}
    >
      {message || (status === "ok" ? "OK" : "")}
    </span>
  );
}

function SecretInput({
  value,
  onChange,
  placeholder,
  id,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  id?: string;
}) {
  const { t } = useTranslation();
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative flex items-center">
      <Input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="pr-9"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-2 flex items-center text-ink-3 transition-colors hover:text-mark"
        tabIndex={-1}
        aria-label={visible ? t("settings.hide") : t("settings.show")}
      >
        {visible ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
      </button>
    </div>
  );
}

/** 排版規格表 —— what the press needs before it can set the type. */
export default function Settings() {
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();

  const [sessdata, setSessdata] = useState(MASK);
  const [proxyList, setProxyList] = useState("");
  const [refreshWindowSize, setRefreshWindowSize] = useState(40);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [sessdataTest, setSessdataTest] = useState<TestStatus>("idle");
  const [sessdataMessage, setSessdataMessage] = useState("");

  const [lang, setLang] = useState<string>(localStorage.getItem("lang") || "zh");

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setSessdata(s.sessdata ? MASK : "");
        setProxyList(s.proxy_list || "");
        setRefreshWindowSize(s.refresh_window_size || 40);
      })
      .catch(() => {
        // Keep defaults; saving still works.
      })
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setSaveError(null);
    try {
      const payload: Record<string, string | number> = {
        proxy_list: proxyList,
        refresh_window_size: refreshWindowSize,
      };
      if (sessdata !== MASK) payload.sessdata = sessdata;

      await api.updateSettings(payload);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setSaveError(t("settings.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  async function handleTestSessdata() {
    setSessdataTest("loading");
    setSessdataMessage("");
    try {
      const res = await api.testSessdata(sessdata);
      const ok = res.status === "ok";
      setSessdataTest(ok ? "ok" : "error");
      setSessdataMessage(res.message || (ok ? t("settings.testOk") : t("settings.testFailed")));
    } catch {
      setSessdataTest("error");
      setSessdataMessage(t("settings.testFailed"));
    }
  }

  if (loading) {
    return <BlankSheet title={t("common.loading")} note={t("blank.loadingNote")} />;
  }

  return (
    <>
      <Masthead
        title={t("settings.title")}
        actions={
          <div className="flex items-center gap-3">
            {saved && <span className="text-note text-pencil">{t("settings.saved")}</span>}
            {saveError && <span className="text-note text-mark">{saveError}</span>}
            <Button variant="default" onClick={handleSave} disabled={saving}>
              {saving && <InkPulse />}
              {t("settings.save")}
            </Button>
          </div>
        }
      />

      <div className="flex max-w-3xl flex-col px-4 pt-6 pb-16 md:px-8">
        <div className="border-t border-rule">
          <SpecRow label={t("settings.bilibili")} help={t("settings.sessdataHelp")}>
            <SecretInput
              id="sessdata"
              value={sessdata}
              onChange={(v) => {
                setSessdata(v);
                setSessdataTest("idle");
                setSessdataMessage("");
              }}
              placeholder="SESSDATA"
            />
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={handleTestSessdata}
                disabled={sessdataTest === "loading"}
              >
                {sessdataTest === "loading" && <InkPulse />}
                {t("settings.validateSessdata")}
              </Button>
              <TestResult status={sessdataTest} message={sessdataMessage} />
            </div>
          </SpecRow>

          <SpecRow label={t("settings.proxy")} help={t("settings.proxyHelp")}>
            <textarea
              value={proxyList}
              onChange={(e) => setProxyList(e.target.value)}
              placeholder={t("settings.proxyPlaceholder")}
              rows={4}
              aria-label={t("settings.proxy")}
              className="w-full resize-y border border-rule-2 bg-transparent px-2.5 py-2 font-sans text-ui leading-relaxed text-ink outline-none transition-colors placeholder:text-ink-3 focus-visible:border-mark focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mark/40"
            />
          </SpecRow>

          <SpecRow
            label={t("settings.refreshWindow")}
            help={t("settings.refreshWindowHelp")}
          >
            <Input
              type="number"
              min={30}
              max={50}
              value={refreshWindowSize}
              onChange={(e) => {
                const next = Number(e.target.value);
                if (Number.isFinite(next)) {
                  setRefreshWindowSize(Math.min(50, Math.max(30, next)));
                }
              }}
              aria-label={t("settings.refreshWindow")}
              className="w-28 tabular-nums"
            />
          </SpecRow>

          <SpecRow label={t("settings.appearance")}>
            <div className="flex flex-col gap-1.5">
              <Label className="column-label">{t("settings.theme")}</Label>
              <ToggleGroup
                value={[theme]}
                onValueChange={(vals: string[]) => vals.length && setTheme(vals[0] as Theme)}
                variant="outline"
              >
                <ToggleGroupItem value="light">{t("settings.light")}</ToggleGroupItem>
                <ToggleGroupItem value="dark">{t("settings.dark")}</ToggleGroupItem>
                <ToggleGroupItem value="system">{t("settings.system")}</ToggleGroupItem>
              </ToggleGroup>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="column-label">{t("settings.language")}</Label>
              <Select
                value={lang}
                onValueChange={(v: string | null) => {
                  if (!v) return;
                  setLang(v);
                  i18n.changeLanguage(v);
                  localStorage.setItem("lang", v);
                }}
              >
                <SelectTrigger className="w-40">
                  <SelectValue>{lang === "zh" ? "中文" : "English"}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="zh">中文</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </SpecRow>

          <SpecRow label={t("settings.data")} help={t("settings.dataHelp")}>
            <div>
              <Dialog>
                <DialogTrigger render={<Button variant="destructive" size="sm" />}>
                  {t("settings.clearAll")}
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{t("settings.clearAll")}</DialogTitle>
                    <DialogDescription>{t("settings.clearConfirm")}</DialogDescription>
                  </DialogHeader>
                  <DialogFooter>
                    <DialogClose render={<Button variant="outline" />}>
                      {t("common.cancel")}
                    </DialogClose>
                    <DialogClose
                      render={
                        <Button
                          variant="destructive"
                          onClick={() => {
                            localStorage.clear();
                            window.location.reload();
                          }}
                        />
                      }
                    >
                      {t("common.confirm")}
                    </DialogClose>
                  </DialogFooter>
                </DialogContent>
              </Dialog>
            </div>
          </SpecRow>
        </div>

      </div>
    </>
  );
}
