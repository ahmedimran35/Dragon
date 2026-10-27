import {
  Bell,
  Box,
  Brain,
  Check,
  ChevronRight,
  Clapperboard,
  Code2,
  DatabaseZap,
  Download,
  Info,
  LogOut,
  MessageSquare,
  Moon,
  Palette,
  Plug,
  Puzzle,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Smile,
  Sparkles,
  TerminalSquare,
  Zap,
} from "lucide-react";
import { Fragment, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { api, setToken } from "../api";
import { DRAGON } from "../avatars";
import { setDeveloperTools, useDeveloperTools } from "../devtools";
import { setShowSteps, useShowSteps } from "../steps";
import { clearMarks, filterPages, hitLabel, markMatches, queryWords } from "../settings-search";
import { AVATAR_COLORS } from "../components/AvatarPicker";
import { IdentityForm, identityBody, identityOf, type Identity } from "../components/IdentityForm";
import { PageBar } from "../components/BackBar";
import { getLocale, LOCALES, setLocaleSetting, useLocaleSetting, useT } from "../i18n";
import { has, regionOf, unavailableLine, useProviders } from "../providers";
import { setThemeSetting, useThemeSetting } from "../theme";
import { disablePush, enablePush, pushState, type PushState } from "../push";
import { useStore } from "../store";
import type { Proactivity, PushInfo } from "../types";
import { DragonCaption, DragonCard, DragonDivider, DragonRow } from "../components/DragonList";
import { useWide } from "../useWide";
import { cx } from "../util";
import { Toggle } from "../components/Form";

const settingsInput = "w-full rounded-2xl bg-surface-2 px-3.5 py-2.5 outline-none focus:ring-2 focus:ring-accent/40";

const MODES: Array<{ id: "ask" | "strict" | "auto"; title: string; text: string; icon: ReactNode }> = [
  {
    id: "ask",
    title: "Balanced",
    text: "Browse, read and write files freely; stop for anything hard to undo: email, purchases, shell commands.",
    icon: <ShieldCheck size={18} />,
  },
  {
    id: "strict",
    title: "Cautious",
    text: "Also ask before moderate actions like fetching web pages or writing files.",
    icon: <Shield size={18} />,
  },
  {
    id: "auto",
    title: "Hands-off",
    text: "Approve everything automatically except explicit deny rules. For trusted, unattended runs only.",
    icon: <ShieldAlert size={18} />,
  },
];

export function SettingsScreen() {
  const { state, refreshSettings, setTab, toast } = useStore();
  const s = state.settings;
  const [identity, setIdentity] = useState<Identity>(() => identityOf(state.profile, DRAGON, AVATAR_COLORS[0]));
  const [saving, setSaving] = useState(false);
  const t = useT();
  const localeSetting = useLocaleSetting();
  const themeSetting = useThemeSetting();
  // the four selects and the label beside each: one id per pair, so the label names the control
  const ids = useId();
  const intervalId = `${ids}-interval`;
  const themeId = `${ids}-theme`;
  const appLangId = `${ids}-app-language`;
  const replyLangId = `${ids}-reply-language`;

  useEffect(() => {
    if (!s) void refreshSettings();
  }, [s, refreshSettings]);

  useEffect(() => {
    if (state.profile) setIdentity(identityOf(state.profile, "", AVATAR_COLORS[0]));
  }, [state.profile]);

  const update = async (body: Record<string, unknown>, msg?: string) => {
    setSaving(true);
    try {
      await api.updateSettings(body);
      await refreshSettings();
      if (msg) toast(msg);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const saved = identityOf(state.profile, "", AVATAR_COLORS[0]);
  const dirty = !!state.profile && (Object.keys(identity) as (keyof Identity)[]).some((k) => identity[k] !== saved[k]);
  const name = state.profile?.name ?? "Dragon";
  const developer = useDeveloperTools();
  const steps = useShowSteps();
  // One page on a wide window (the sections down the left); on a narrow one the list of
  // rows, each opening its own page.
  const wide = useWide() && !state.lite;
  const [page, setPage] = useState<SectionId | null>(null);
  // the settings search: the sections by their title, and the words in the sections
  // themselves (../settings-search)
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<Array<{ element: HTMLElement; label: string }>>([]);
  const bodyRef = useRef<HTMLDivElement | null>(null);
  const navRef = useRef<HTMLElement | null>(null);
  const sections: Array<{ id: SectionId; title: string }> = [
    { id: "who", title: name },
    { id: "sentinel", title: t("Safety · Sentinel") },
    { id: "proactivity", title: t("Proactivity") },
    { id: "notifications", title: t("Notifications") },
    { id: "model", title: t("Model") },
    { id: "appearance", title: t("Appearance") },
    { id: "data", title: t("Data controls") },
    { id: "developer", title: t("Developer") },
    { id: "about", title: t("About") },
  ];
  const show = (id: SectionId) => wide || page === id;
  const searching = queryWords(query).length > 0;
  const pageHits = filterPages(
    sections.map((sec) => ({ id: sec.id, label: sec.title })),
    query,
  );
  const matching = new Set(pageHits.map((p) => p.id));

  // The query on the sections in view: the words that match are marked where they
  // stand and listed under the field, so a setting is found by its own words. The
  // first hit is scrolled to when the query changes; a settings save re-marks
  // without moving the page.
  const asked = useRef("");
  useEffect(() => {
    const root = bodyRef.current;
    if (root === null) {
      setHits([]);
      return;
    }
    const marked = markMatches(root, query);
    // a row's title and the line under it are one hit, not two
    const grouped = new Map<HTMLElement, { element: HTMLElement; label: string }>();
    for (const element of marked) {
      const key = element.parentElement ?? element;
      if (!grouped.has(key)) grouped.set(key, { element, label: hitLabel(element) });
    }
    setHits([...grouped.values()]);
    const queryChanged = asked.current !== query;
    if (queryChanged && queryWords(query).length > 0) {
      marked[0]?.scrollIntoView({ block: "center" });
      // the hits are listed at the top of the nav, so the nav goes back to the top
      // when the query starts, or they would be out of sight
      if (asked.current.trim() === "") navRef.current?.scrollTo({ top: 0 });
    }
    asked.current = query;
    return () => {
      clearMarks(root);
    };
  }, [query, s, wide]);

  const onSearchKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      // the field clears first; an empty field leaves Escape to the page
      if (query.trim() === "") return;
      event.preventDefault();
      setQuery("");
      return;
    }
    if (event.key !== "Enter") return;
    event.preventDefault();
    const firstPage = pageHits[0];
    if (firstPage !== undefined) {
      document.getElementById(firstPage.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    hits[0]?.element.scrollIntoView({ block: "center" });
  };

  // `#developer` (the sidebar's menu), `#who` (the agent page's Edit) and the other section
  // ids land on that section — once the settings are in, so the sections above it have
  // their final height; at narrow widths they open that page.
  const [wanted, setWanted] = useState<SectionId | null>(() => {
    const id = window.location.hash.slice(1);
    return SECTION_IDS.includes(id as SectionId) ? (id as SectionId) : null;
  });
  useEffect(() => {
    if (!wanted || !s) return;
    setWanted(null);
    history.replaceState(null, "", window.location.pathname + window.location.search);
    if (!wide) {
      setPage(wanted);
      return;
    }
    requestAnimationFrame(() => document.getElementById(wanted)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, [wanted, s, wide]);

  if (!wide && page === null) {
    return <SettingsHome onOpen={setPage} sections={sections} query={query} onQuery={setQuery} />;
  }
  const current = sections.find((x) => x.id === page);

  return (
    <div className="flex h-full flex-col">
      {wide ? (
        <PageBar title={t("Settings")} description={t("Its name and look, how careful it is, how often it speaks up.")} />
      ) : (
        <PageBar title={current?.title ?? t("Settings")} onBack={() => setPage(null)} backLabel={t("Settings")} />
      )}

      <div className="flex min-h-0 flex-1">
        {/* on a wide window, the sections down the left — the shape of Dragon's settings */}
        {wide && (
          <nav ref={navRef} className="flex max-h-full w-[188px] shrink-0 flex-col gap-0.5 self-start overflow-y-auto pl-4 pr-2 pt-1" aria-label={t("Settings")}>
            {/* the search: the sections by their title, and the words in the sections themselves */}
            <div className="px-1 pb-1">
              <div className="flex items-center gap-2 rounded-xl bg-surface-2 px-2.5 py-1.5">
                <Search size={14} className="shrink-0 text-muted" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.currentTarget.value)}
                  onKeyDown={onSearchKey}
                  placeholder={t("Search settings")}
                  aria-label={t("Search settings")}
                  className="w-full bg-transparent text-[13px] outline-none placeholder:text-muted"
                />
              </div>
            </div>
            {searching && (
              <div className="pb-1">
                {hits.length > 0 && (
                  <>
                    <div className="px-3 pb-0.5 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted">{t("On this page")}</div>
                    {hits.map((hit, index) => (
                      <button
                        key={`${index}-${hit.label}`}
                        type="button"
                        onClick={() => hit.element.scrollIntoView({ block: "center" })}
                        className="block w-full truncate rounded-xl px-3 py-1.5 text-left text-[13px] text-fg/75 hover:bg-surface-2 hover:text-fg"
                      >
                        {hit.label}
                      </button>
                    ))}
                  </>
                )}
                {hits.length === 0 && pageHits.length === 0 && <div className="px-3 py-1.5 text-[13px] text-muted">{t("Nothing matches")}</div>}
              </div>
            )}
            {sections.map((sec) => (
              <button
                key={sec.id}
                type="button"
                onClick={() => document.getElementById(sec.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}
                className={cx(
                  "truncate rounded-xl px-3 py-1.5 text-left text-[13px] font-medium text-fg/75 hover:bg-surface-2 hover:text-fg",
                  searching && matching.has(sec.id) && "bg-accent/10 text-fg",
                )}
              >
                {sec.title}
              </button>
            ))}
          </nav>
        )}
      <div ref={bodyRef} className="flex-1 overflow-y-auto px-4 pb-8 space-y-5">
        {/* who it is */}
        {show("who") && (
        <Section title={name} id="who" plain={!wide}>
          <IdentityForm
            value={identity}
            onChange={setIdentity}
            suggestions={false}
            inputCls={settingsInput}
            onStudio={() => setTab("avatar")}
          />
          <button
            type="button"
            disabled={!dirty || saving}
            onClick={() => void update({ profile: identityBody(identity) }, t("Saved"))}
            className="w-full rounded-2xl bg-accent text-accent-fg py-2.5 font-medium disabled:opacity-40"
          >
            {t("Save")}
          </button>
        </Section>
        )}

        {/* Sentinel */}
        {show("sentinel") && (
        <Section title={t("Safety · Sentinel")} id="sentinel" plain={!wide}>
          <p className="text-[13px] text-muted -mt-1">
            {t("A separate gatekeeper reviews every action. Pick how often it should check in with you.")}
          </p>
          <div className="space-y-2">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => void update({ sentinel_mode: m.id })}
                aria-pressed={s?.sentinel.mode === m.id}
                className={cx(
                  "w-full text-left rounded-2xl border px-3.5 py-3 flex items-start gap-3 transition",
                  s?.sentinel.mode === m.id ? "border-accent bg-accent/8" : "border-border",
                )}
              >
                <div className={cx("mt-0.5", m.id === "auto" ? "text-rose-500" : "text-accent")}>{m.icon}</div>
                <div className="flex-1">
                  <div className="font-medium text-[14.5px]">{t(m.title)}</div>
                  <div className="text-[12.5px] text-muted leading-snug mt-0.5">{t(m.text)}</div>
                </div>
                {s?.sentinel.mode === m.id && <Check size={18} className="text-accent mt-0.5" />}
              </button>
            ))}
          </div>
          {s && (
            <div className="text-[12.5px] text-muted leading-relaxed">
              {t("Always asks before: {tools}.", { tools: s.sentinel.always_ask_tools.map((tool) => t(tool)).join(", ") || t("none") })}{" "}
              {s.sentinel.taint_tracking && t("After reading private data, new network destinations need approval.")}
            </div>
          )}
          {s?.sandbox && (
            <div className="flex items-start gap-2.5 rounded-2xl bg-surface-2/60 px-3.5 py-2.5 text-[12.5px] leading-snug">
              <Box size={15} className={cx("shrink-0 mt-[2px]", s.sandbox.active ? "text-emerald-500" : "text-muted")} />
              <div>
                <div className="font-medium text-fg">
                  {s.sandbox.active ? t("Commands run in a sandbox") : t("Commands run without a sandbox")}
                  <span className="text-muted font-normal"> · {s.sandbox.status}</span>
                </div>
                <div className="text-muted mt-0.5">
                  {s.sandbox.active
                    ? t("Each shell or Python call gets its own namespace: only the workspace is writable, your home directory is not there, and there is no network unless the command needs it.")
                    : s.sandbox.status.includes("container")
                      ? t("Each shell or Python call runs in the workspace with a scrubbed environment; the container is the boundary.")
                      : t("Each shell or Python call runs in the workspace with a scrubbed environment. On Linux, installing bubblewrap gives each one its own namespace.")}
                </div>
              </div>
            </div>
          )}
        </Section>
        )}

        {/* Proactivity */}
        {show("proactivity") && (
        <Section title={t("Proactivity")} id="proactivity" plain={!wide}>
          <ProactivityDial value={state.profile?.proactivity ?? "default"} onChange={(v) => void update({ profile: { proactivity: v } })} />
          <div className="flex items-center gap-3">
            <label htmlFor={intervalId} className="text-[13.5px] flex-1">
              {t("Check-in interval")}
              {state.profile && state.profile.proactivity !== "default" && state.profile.proactivity !== "off" && (
                <span className="block text-[12px] text-muted">
                  {state.profile.proactivity === "low" ? t("Doubled at this level") : t("Halved at this level")}
                </span>
              )}
            </label>
            <select
              id={intervalId}
              value={state.profile?.goal_interval_minutes ?? 60}
              onChange={(e) => void update({ profile: { goal_interval_minutes: Number(e.target.value) } })}
              className="rounded-2xl bg-surface-2 px-3 py-2 text-[13.5px] outline-none"
            >
              {[...new Set([15, 30, 60, 120, 240, 480, 1440, state.profile?.goal_interval_minutes ?? 60])]
                .sort((a, b) => a - b)
                .map((m) => (
                  <option key={m} value={m}>
                    {m < 60 ? t("{n} min", { n: m }) : m % 60 ? `${t("{n} h", { n: Math.floor(m / 60) })} ${t("{n} min", { n: m % 60 })}` : t("{n} h", { n: m / 60 })}
                  </option>
                ))}
            </select>
          </div>
          <QuietHours value={state.profile?.quiet_hours ?? ""} onChange={(v) => void update({ profile: { quiet_hours: v } })} />
        </Section>
        )}

        {/* Notifications */}
        {show("notifications") && (
        <Section title={t("Notifications")} id="notifications" plain={!wide}>
          <PushSettings name={state.profile?.name ?? "Dragon"} />
        </Section>
        )}

        {/* Model */}
        {show("model") && (
        <Section title={t("Model")} id="model" plain={!wide}>
          {s && (
            <button type="button" onClick={() => setTab("connections")} className="w-full text-[13.5px] flex items-center justify-between">
              <span className="text-muted">{t("Provider / model")}</span>
              <span className="font-mono text-[12.5px] flex items-center gap-1">
                {s.llm.model} <ChevronRight size={14} className="text-muted" />
              </span>
            </button>
          )}
          <button type="button" onClick={() => setTab("connections")} className="w-full text-[13.5px] flex items-center justify-between">
            <span className="text-muted">{t("Connections")}</span>
            <span className="text-[12.5px] text-muted flex items-center gap-1">
              {t("E-mail, calendar, browser, MCP servers")} <ChevronRight size={14} />
            </span>
          </button>
        </Section>
        )}

        {/* Appearance: this browser's theme and language, the agent's reply language */}
        {show("appearance") && (
        <Section title={t("Appearance")} id="appearance" plain={!wide}>
          <Toggle
            label={t("Show the agent's steps")}
            hint={t("Every tool it uses becomes a chip in the chat. Off, the chat keeps to the conversation and the line under the name says what it is on. This browser only.")}
            checked={steps}
            onChange={setShowSteps}
          />
          <Toggle
            label={t("Show thinking")}
            hint={t("Reveal the model's reasoning under each reply when the provider exposes it.")}
            checked={!!s?.agent.show_thinking}
            onChange={(v) => void update({ show_thinking: v })}
          />
          <div className="flex items-center gap-3">
            <label htmlFor={themeId} className="text-[13.5px] flex-1">
              {t("Appearance")}
              <span className="block text-[12px] text-muted">{t("This browser only")}</span>
            </label>
            <select
              id={themeId}
              value={themeSetting}
              onChange={(e) => setThemeSetting(e.target.value as typeof themeSetting)}
              className="rounded-2xl bg-surface-2 px-3 py-2 text-[13.5px] outline-none"
            >
              <option value="light">{t("Light")}</option>
              <option value="dark">{t("Dark")}</option>
              <option value="system">{t("Follow the system")}</option>
            </select>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor={appLangId} className="text-[13.5px] flex-1">
              {t("App language")}
              <span className="block text-[12px] text-muted">{t("This browser only")}</span>
            </label>
            <select
              id={appLangId}
              value={localeSetting}
              onChange={(e) => setLocaleSetting(e.target.value as typeof localeSetting)}
              className="rounded-2xl bg-surface-2 px-3 py-2 text-[13.5px] outline-none"
            >
              {LOCALES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.value === "auto" ? t("Auto") : l.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-3">
            <label htmlFor={replyLangId} className="text-[13.5px] flex-1">
              {t("Reply language")}
              <span className="block text-[12px] text-muted">{t("What {name} writes in", { name: state.profile?.name ?? "Dragon" })}</span>
            </label>
            <select
              id={replyLangId}
              value={s?.agent.language ?? "auto"}
              onChange={(e) => void update({ language: e.target.value })}
              className="rounded-2xl bg-surface-2 px-3 py-2 text-[13.5px] outline-none"
            >
              <option value="auto">{t("Match mine")}</option>
              <option value="English">English</option>
              <option value="中文">中文</option>
              <option value="日本語">日本語</option>
              <option value="Español">Español</option>
              <option value="Deutsch">Deutsch</option>
              <option value="Français">Français</option>
            </select>
          </div>
        </Section>
        )}

        {/* Data controls: the agent's data as one zip */}
        {show("data") && (
        <Section title={t("Data controls")} id="data" plain={!wide}>
          <ExportData />
        </Section>
        )}

        {/* The developer side, off unless asked for */}
        {show("developer") && (
        <Section title={t("Developer")} id="developer" plain={!wide}>
          <Toggle
            label={t("Developer tools")}
            hint={t("The Coding screen (Cursor, Codex and the other coding agents on this computer) in the sidebar, and the runtime's address below. This browser only.")}
            checked={developer}
            onChange={setDeveloperTools}
          />
          {developer && (
            <div className="text-[13px] text-muted space-y-1">
              <div className="break-all">
                {t("Runtime:")} {window.location.origin} · <span className="text-fg/70">{t("the token is in the server_token file in the data folder")}</span>
              </div>
              <div>{t("The command line and the API")} · {t("see docs/cli.md in the repository")}</div>
            </div>
          )}
        </Section>
        )}

        {/* About */}
        {show("about") && (
        <Section title={t("About")} id="about" plain={!wide}>
          <div className="text-[13px] text-muted space-y-1">
            <div className="text-fg">{t("Dragon {version}", { version: state.version })}</div>
            {s && <div className="break-all">{t("Data:")} {s.data_dir}</div>}
            {s && <div className="break-all">{t("Workspace:")} {s.agent.workspace}</div>}
            <div>{state.connected ? t("Connected") : t("Reconnecting…")}</div>
          </div>
          <button
            type="button"
            onClick={() => {
              setToken("");
              window.location.reload();
            }}
            className="w-full rounded-2xl border border-border py-2.5 text-[14px] font-medium flex items-center justify-center gap-2 text-muted"
          >
            <LogOut size={16} /> {t("Forget this browser's access token")}
          </button>
        </Section>
        )}
      </div>
      </div>
    </div>
  );
}

type SectionId = "who" | "sentinel" | "proactivity" | "notifications" | "model" | "appearance" | "data" | "developer" | "about";
const SECTION_IDS: SectionId[] = ["who", "sentinel", "proactivity", "notifications", "model", "appearance", "data", "developer", "about"];

/**
 * The settings home: cards of outlined-glyph rows on the grey canvas — the model, the
 * agent, how it behaves, the app, about — each row opening its own page or screen.
 */
function SettingsHome({
  onOpen,
  sections,
  query,
  onQuery,
}: {
  onOpen: (id: SectionId) => void;
  sections: Array<{ id: SectionId; title: string }>;
  query: string;
  onQuery: (value: string) => void;
}) {
  const { state, setTab } = useStore();
  const t = useT();
  const s = state.settings;
  // what the configured providers cover (contract C11), from the runtime; null on an older one
  const providers = useProviders();
  const name = state.profile?.name ?? "Dragon";
  const themeSetting = useThemeSetting();
  const mode = s?.sentinel.mode;
  const modeLabel = mode === "ask" ? t("Balanced") : mode === "strict" ? t("Cautious") : mode === "auto" ? t("Hands-off") : "";
  const level = state.profile?.proactivity ?? "default";
  const levelLabel = level === "off" ? t("Off") : level === "low" ? t("Low") : level === "high" ? t("High") : t("Default");
  const themeLabel = themeSetting === "dark" ? t("Dark") : themeSetting === "light" ? t("Light") : t("Follow the system");
  // The settings search here: the sections by their title. Their words are not rendered
  // on this screen, so the title is all a query can answer here; the query stands when a
  // section opens, and its words are marked on that page.
  const homeSearching = queryWords(query).length > 0;
  const sectionHits = filterPages(
    sections.map((sec) => ({ id: sec.id, label: sec.title })),
    query,
  );
  const onHomeSearchKey = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") {
      if (query.trim() === "") return;
      event.preventDefault();
      onQuery("");
      return;
    }
    if (event.key !== "Enter") return;
    event.preventDefault();
    const first = sectionHits[0];
    if (first !== undefined) onOpen(first.id);
  };
  const searchBox = (
    <div className="px-4 pb-1 pt-1">
      <div className="flex items-center gap-2 rounded-xl bg-surface-2 px-2.5 py-2">
        <Search size={15} className="shrink-0 text-muted" />
        <input
          type="text"
          value={query}
          onChange={(e) => onQuery(e.currentTarget.value)}
          onKeyDown={onHomeSearchKey}
          placeholder={t("Search settings")}
          aria-label={t("Search settings")}
          className="w-full bg-transparent text-[13.5px] outline-none placeholder:text-muted"
        />
      </div>
    </div>
  );
  if (homeSearching) {
    return (
      <div className="flex h-full flex-col">
        <PageBar title={t("Settings")} />
        {searchBox}
        <div className="flex-1 overflow-y-auto px-4 pb-8 pt-2">
          {sectionHits.length > 0 ? (
            <DragonCard>
              {sectionHits.map((sec, index) => (
                <Fragment key={sec.id}>
                  {index > 0 && <DragonDivider />}
                  <DragonRow label={sec.label} onClick={() => onOpen(sec.id)} />
                </Fragment>
              ))}
            </DragonCard>
          ) : (
            <div className="px-1 pt-2 text-[13.5px] text-muted">{t("Nothing matches")}</div>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="flex h-full flex-col">
      <PageBar title={t("Settings")} />
      {searchBox}
      <div className="flex-1 overflow-y-auto pb-8 pt-2">
        {/* the model */}
        <DragonCard className="mb-3">
          <button type="button" onClick={() => setTab("connections")} className="flex w-full items-center gap-3 px-4 py-3.5 text-left hover:bg-surface-2/60">
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[16px] font-medium leading-[21px]">{s?.llm.model || t("No model yet")}</span>
              <span className="mt-0.5 block truncate text-[12.5px] leading-4 text-muted">
                {s ? s.llm.provider : t("Add a provider and pick its models")}
              </span>
            </span>
            <span className="text-[14px] font-medium text-accent">{t("Change")}</span>
          </button>
          <DragonDivider />
          <DragonRow
            icon={<Clapperboard size={22} />}
            label={t("Image & video models")}
            value={
              has(providers, "image") === false
                ? unavailableLine(t, "image", regionOf(getLocale()), getLocale())
                : has(providers, "video") === false
                  ? unavailableLine(t, "video", regionOf(getLocale()), getLocale())
                  : undefined
            }
            onClick={() => setTab("connections")}
          />
        </DragonCard>

        {/* the agent */}
        <DragonCard className="mb-3">
          <DragonRow icon={<Sparkles size={22} />} label={t("Name & personality")} value={name} onClick={() => onOpen("who")} />
          <DragonDivider />
          <DragonRow icon={<Smile size={22} />} label={t("Avatar")} onClick={() => setTab("avatar")} />
          <DragonDivider />
          <DragonRow icon={<Brain size={22} />} label={t("Memory")} onClick={() => setTab("memory")} />
          {s?.skills?.enabled !== false && (
            <>
              <DragonDivider />
              <DragonRow icon={<Puzzle size={22} />} label={t("Skills")} value={s ? String(s.skills.count) : undefined} onClick={() => setTab("skills")} />
            </>
          )}
          <DragonDivider />
          <DragonRow icon={<Plug size={22} />} label={t("Connections")} value={s?.connectors.mcp.length ? `${s.connectors.mcp.length} MCP` : undefined} onClick={() => setTab("connections")} />
          <DragonDivider />
          <DragonRow icon={<MessageSquare size={22} />} label={t("Chat apps")} onClick={() => setTab("channels")} />
          <DragonDivider />
          <DragonRow icon={<TerminalSquare size={22} />} label={t("Coding agents")} onClick={() => setTab("coding")} />
        </DragonCard>

        {/* how it behaves */}
        <DragonCard className="mb-3">
          <DragonRow icon={<ShieldCheck size={22} />} label={t("Safety · Sentinel")} value={modeLabel} onClick={() => onOpen("sentinel")} />
          <DragonDivider />
          <DragonRow icon={<Zap size={22} />} label={t("Proactivity")} value={levelLabel} onClick={() => onOpen("proactivity")} />
          <DragonDivider />
          <DragonRow icon={<Bell size={22} />} label={t("Notifications")} onClick={() => onOpen("notifications")} />
        </DragonCard>

        {/* the app */}
        <DragonCard className="mb-3">
          <DragonRow icon={<Palette size={22} />} label={t("Appearance")} value={themeLabel} onClick={() => onOpen("appearance")} />
          <DragonDivider />
          <DragonRow icon={<DatabaseZap size={22} />} label={t("Data controls")} onClick={() => onOpen("data")} />
          <DragonDivider />
          <DragonRow icon={<Code2 size={22} />} label={t("Developer")} onClick={() => onOpen("developer")} />
        </DragonCard>

        {/* about */}
        <DragonCard className="mb-3">
          <DragonRow icon={<Info size={22} />} label={t("About Dragon")} onClick={() => onOpen("about")} />
        </DragonCard>
        <DragonCaption>Dragon {state.version}</DragonCaption>
      </div>
    </div>
  );
}

/** Web Push: on / off, what stands in the way, and a test button. */
function PushSettings({ name }: { name: string }) {
  const { toast } = useStore();
  const [info, setInfo] = useState<PushInfo | null>(null);
  const [status, setStatus] = useState<PushState>("off");
  const [busy, setBusy] = useState(false);
  const t = useT();

  const refresh = async () => {
    setStatus(await pushState());
    try {
      setInfo(await api.push());
    } catch {
      /* older server */
    }
  };
  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = async () => {
    if (!info) return;
    setBusy(true);
    try {
      const next = status === "on" ? await disablePush() : await enablePush(info.public_key);
      setStatus(next);
      if (next === "denied") toast(t("Notifications are blocked for this site in the browser settings"));
      await refresh();
    } catch (e) {
      const err = e as Error;
      toast(
        err.name === "AbortError"
          ? t("This browser has no push service (embedded browsers often don't). Use Chrome, Edge, Firefox, or Safari 16.4+ on iOS.")
          : err.message,
      );
    } finally {
      setBusy(false);
    }
  };

  const test = async () => {
    try {
      const r = await api.pushTest();
      toast(r.ok ? t("Sent. It should arrive in a moment") : r.error ?? t("Could not send"));
    } catch (e) {
      toast((e as Error).message);
    }
  };

  const blocked =
    status === "unsupported"
      ? t("This browser cannot receive push notifications.")
      : status === "insecure"
        ? t("Notifications need https:// (or localhost). Over plain http on your LAN the app works, this part stays off; see docs/deployment.md.")
        : status === "denied"
          ? t("Blocked for this site. Allow notifications in the browser's site settings, then try again.")
          : info && !info.available
            ? t("The server was installed without pywebpush.")
            : "";

  return (
    <>
      <Toggle
        label={t("Let {name} notify this browser", { name })}
        hint={t("Approvals, questions, finished background work and check-ins; nothing while the app is on screen.")}
        checked={status === "on"}
        onChange={() => void toggle()}
        disabled={busy || !!blocked}
      />
      {blocked && <div className="text-[12.5px] text-muted">{blocked}</div>}
      {info && info.subscriptions > 0 && (
        <div className="flex items-center justify-between text-[12.5px] text-muted">
          <span>
            {info.subscriptions === 1 ? t("1 subscription") : t("{n} subscriptions", { n: info.subscriptions })}
          </span>
          <button type="button" onClick={() => void test()} className="text-accent font-medium">
            {t("Send a test")}
          </button>
        </div>
      )}
      <div className="text-[12.5px] text-muted">{t("In a phone browser, add the app to the home screen first; the icon then shows a badge and notifications open the right chat.")}</div>
    </>
  );
}

/** The agent's data as one zip (parity note 37): the runtime answers with the file itself. */
function ExportData() {
  const { toast } = useStore();
  const [busy, setBusy] = useState(false);
  const t = useT();
  const run = async () => {
    setBusy(true);
    try {
      const { blob, name } = await api.exportData();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-1.5">
      <div className="text-[12.5px] text-muted leading-snug">
        {t("Everything this agent holds: conversations, memory, goals, files and settings, as one zip.")}
      </div>
      <button type="button" disabled={busy} onClick={() => void run()} className={cx("inline-flex items-center gap-2 rounded-2xl border border-border px-3.5 py-2 text-[13.5px] font-medium", busy && "opacity-60")}>
        <Download size={15} /> {t("Export data")}
      </button>
    </div>
  );
}

const LEVELS: Array<{ id: Proactivity; title: string; text: string }> = [
  { id: "off", title: "Off", text: "Only works when you ask." },
  { id: "low", title: "Low", text: "Checks in half as often; speaks up only when a step is done or it needs you." },
  { id: "default", title: "Default", text: "Works on goals on schedule; reports real progress, stays quiet otherwise." },
  { id: "high", title: "High", text: "Checks in twice as often and always reports, even 'still on track'." },
];

export function ProactivityDial({ value, onChange }: { value: Proactivity; onChange: (v: Proactivity) => void }) {
  const t = useT();
  const current = LEVELS.find((l) => l.id === value) ?? LEVELS[2];
  return (
    <div>
      <div className="flex items-center gap-3">
        <div className="flex-1 text-[13px] text-muted leading-snug">{t(current.text)}</div>
      </div>
      <div className="mt-2 grid grid-cols-4 gap-1 rounded-2xl bg-surface-2 p-1">
        {LEVELS.map((l) => (
          <button
            key={l.id}
            type="button"
            onClick={() => onChange(l.id)}
            aria-pressed={value === l.id}
            className={cx(
              "rounded-xl py-1.5 text-[13px] font-medium transition",
              value === l.id ? "bg-surface shadow-sm text-accent" : "text-muted",
            )}
          >
            {t(l.title)}
          </button>
        ))}
      </div>
    </div>
  );
}

export function QuietHours({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [start, end] = value ? value.split("-") : ["", ""];
  const on = !!value;
  const t = useT();
  const set = (s: string, e: string) => onChange(s && e ? `${s}-${e}` : "");
  return (
    <div>
      <label className="flex items-start gap-3 cursor-pointer">
        <div className="flex-1">
          <div className="text-[14px] flex items-center gap-1.5">
            <Moon size={15} className="text-muted" /> {t("Quiet hours")}
          </div>
          <div className="text-[12.5px] text-muted leading-snug">{t("No background work in this window; anything due waits until it ends.")}</div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          onClick={() => set(on ? "" : "22:00", on ? "" : "08:00")}
          className={cx("relative mt-0.5 h-7 w-12 shrink-0 rounded-full transition", on ? "bg-accent" : "bg-surface-2 border border-border")}
        >
          <span className={cx("absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition", on ? "left-[22px]" : "left-0.5")} />
        </button>
      </label>
      {on && (
        <div className="mt-2 flex items-center gap-2 text-[13.5px]">
          <span className="text-muted">{t("From")}</span>
          <input type="time" value={start} onChange={(e) => set(e.target.value, end)} aria-label={t("Quiet hours start")} className="rounded-xl bg-surface-2 px-2.5 py-1.5 outline-none" />
          <span className="text-muted">{t("to")}</span>
          <input type="time" value={end} onChange={(e) => set(start, e.target.value)} aria-label={t("Quiet hours end")} className="rounded-xl bg-surface-2 px-2.5 py-1.5 outline-none" />
        </div>
      )}
    </div>
  );
}

/** A settings card; `plain` is the narrow page, where the bar above already names it. */
function Section({ title, children, id, plain = false }: { title: string; children: ReactNode; id?: string; plain?: boolean }) {
  return (
    <section id={id} className={cx("space-y-3 scroll-mt-4", plain ? "pt-1" : "rounded-3xl bg-surface border border-border/70 shadow-sm p-4")}>
      {!plain && <h2 className="text-[12px] font-semibold uppercase tracking-wide text-muted">{title}</h2>}
      {children}
    </section>
  );
}

