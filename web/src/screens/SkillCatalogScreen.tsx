import { Check, Download, ExternalLink, Loader2, RotateCw, Search, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { DragonRoundButton } from "../components/DragonHeader";
import { Toggle } from "../components/Form";
import { LoadError } from "../components/LoadError";
import { PageBar } from "../components/PageBar";
import { useT } from "../i18n";
import { useStore } from "../store";
import type { CatalogStatus, SkillCatalogData } from "../types";
import { relativeTime } from "../util";

/**
 * The public AgenticSkills directory. The catalog is read from its public pages; each
 * import goes through Dragon's own SKILL.md importer and lands in <data_dir>/skills.
 * New skills are added off, so none of this text reaches the model until switched on.
 */
export function SkillCatalogScreen({ onBack }: { onBack: () => void }) {
  const { toast } = useStore();
  const t = useT();
  const [data, setData] = useState<SkillCatalogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState("");
  const [savingAuto, setSavingAuto] = useState(false);

  const load = useCallback(async (refresh = false) => {
    try {
      setData(await api.skillCatalog(refresh));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  // A background import-all updates its own progress; poll only while it is running.
  useEffect(() => {
    if (!data?.status.running) return;
    const timer = window.setInterval(() => {
      api.skillCatalogStatus()
        .then((status: CatalogStatus) => {
          setData((current) => (current ? { ...current, status } : current));
          if (!status.running) void load();
        })
        .catch(() => undefined);
    }, 1500);
    return () => window.clearInterval(timer);
  }, [data?.status.running, load]);

  const install = async (slug: string, name: string) => {
    setBusy(slug);
    try {
      await api.importCatalogSkill(slug);
      setData((current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.slug === slug ? { ...item, installed: true, skill: name.toLowerCase().replace(/\s+/g, "-") } : item
              ),
            }
          : current
      );
      toast(t("{name} added. Switch it on in My skills when you want the agent to use it.", { name }));
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const importAll = async () => {
    setBusy("all");
    try {
      setData((current) => (current ? { ...current, status: { ...current.status, running: true } } : current));
      await api.importAllCatalogSkills();
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const setAuto = async (enabled: boolean) => {
    setSavingAuto(true);
    try {
      setData(await api.setCatalogAuto(enabled));
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setSavingAuto(false);
    }
  };

  const items = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q || !data) return data?.items ?? [];
    return data.items.filter(
      (item) => item.name.toLowerCase().includes(q) || item.description.toLowerCase().includes(q) || item.slug.includes(q)
    );
  }, [data, query]);

  const status = data?.status;
  const installed = data?.items.filter((item) => item.installed).length ?? 0;

  return (
    <div className="flex h-full flex-col">
      <PageBar
        title={t("Skill directory")}
        backLabel={t("Skills")}
        onBack={onBack}
        description={t("Free, open-source SKILL.md recipes from agenticskills.io. Imported skills start off; switch one on in My skills when you want the agent to follow it.")}
        actions={
          <DragonRoundButton small onClick={() => void load(true)} label={t("Refresh directory")}>
            <RotateCw size={19} />
          </DragonRoundButton>
        }
      />
      <div className="flex-1 overflow-y-auto px-4 pb-7">
        {data === null && error && <LoadError message={error} onRetry={() => void load(true)} />}
        {data === null && !error && (
          <div className="py-12 flex justify-center text-muted"><Loader2 className="animate-spin" size={20} /></div>
        )}
        {data && (
          <>
            <section className="rounded-3xl border border-border/70 bg-surface px-4 py-3.5">
              <div className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-muted">
                <ShieldCheck size={14} /> {t("Keep current")}
              </div>
              <div className="mt-2">
                <Toggle
                  label={t("Add new skills automatically")}
                  hint={t("Check the directory every six hours and add anything new, off by default.")}
                  checked={data.auto_sync}
                  onChange={(v) => void setAuto(v)}
                  disabled={savingAuto}
                />
              </div>
              <p className="mt-2 text-[12px] text-muted">
                {t("{n} of {total} installed", { n: installed, total: data.total })}
                {data.last_sync ? ` · ${t("checked {when}", { when: relativeTime(data.last_sync) })}` : ""}
              </p>
              {status?.running ? (
                <div className="mt-3">
                  <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${status.total ? Math.round((status.done / status.total) * 100) : 0}%` }} />
                  </div>
                  <div className="mt-1.5 text-[12px] text-muted">
                    {t("Adding {n} of {total}…", { n: status.done, total: status.total })}
                  </div>
                  {status.errors.length > 0 && <div className="mt-1 text-[12px] text-rose-600 dark:text-rose-300">{status.errors[0]}</div>}
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => void importAll()}
                  disabled={busy === "all" || installed === data.total}
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-full bg-surface-2 py-2.5 text-[14px] font-medium disabled:opacity-60"
                >
                  <Download size={16} /> {t("Add all {n} skills", { n: data.total })}
                </button>
              )}
              {data.last_error && <div className="mt-2 text-[12px] text-rose-600 dark:text-rose-300">{data.last_error}</div>}
            </section>

            <label className="mt-4 flex items-center gap-2 rounded-2xl bg-surface-2 px-3.5 py-2.5">
              <Search size={17} className="shrink-0 text-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t("Search the directory")}
                aria-label={t("Search the directory")}
                className="w-full bg-transparent text-[15px] outline-none placeholder:text-muted"
              />
            </label>

            <div className="mt-3 space-y-2">
              {items.map((item) => (
                <div key={item.slug} className="rounded-3xl border border-border/70 bg-surface px-4 py-3">
                  <div className="flex items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-[15px] leading-snug">{item.name}</span>
                        {item.installed && (
                          <span className="flex items-center gap-1 rounded-full bg-accent/12 px-2 py-0.5 text-[11px] font-medium text-accent">
                            <Check size={11} /> {t("Added")}
                          </span>
                        )}
                      </div>
                      {item.description && <p className="mt-1 text-[13px] leading-snug text-muted">{item.description}</p>}
                      <a href={item.url} target="_blank" rel="noreferrer" className="mt-1.5 inline-flex items-center gap-1 text-[12px] text-accent">
                        {t("View source")} <ExternalLink size={12} />
                      </a>
                    </div>
                  </div>
                  {!item.installed && (
                    <button
                      type="button"
                      onClick={() => void install(item.slug, item.name)}
                      disabled={busy !== ""}
                      className="mt-2 flex w-full items-center justify-center gap-2 rounded-full bg-surface-2 py-2 text-[13px] font-medium disabled:opacity-60"
                    >
                      {busy === item.slug ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
                      {t("Add")}
                    </button>
                  )}
                </div>
              ))}
              {items.length === 0 && query && (
                <div className="py-10 text-center text-[14px] text-muted">{t("No skills match that search.")}</div>
              )}
            </div>
            <p className="px-1 pt-4 text-[12px] text-muted">
              {t("Directory by agenticskills.io. Each skill keeps its own licence and upstream source; review them before use.")}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
