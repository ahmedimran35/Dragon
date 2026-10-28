import { Check, Loader2, Plus, Trash2 } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { DRAGON } from "../avatars";
import { botMood, defaultBot, DEFAULT_BOT_ID, type Presence, type PresenceInput } from "../bots";
import { Avatar } from "../components/Avatar";
import { AVATAR_COLORS, AvatarPicker } from "../components/AvatarPicker";
import { PageBar } from "../components/BackBar";
import {
  IdentityNameFields,
  IdentityVoice,
  commLabel,
  identityBody,
  identityOf,
  toneLabel,
  type Identity,
} from "../components/IdentityForm";
import { useT } from "../i18n";
import { useStore } from "../store";
import type { Bot } from "../types";
import { cx } from "../util";

const botInput = "w-full rounded-2xl bg-surface-2 px-3.5 py-2.5 outline-none transition focus:ring-2 focus:ring-accent/40";

/** The presence dot's colour: working amber, waiting rose, idle a quiet green. */
const PRESENCE_DOT: Record<Presence, string> = {
  working: "bg-amber-400",
  waiting: "bg-rose-500",
  idle: "bg-emerald-500",
};
/** What the dot stands for, in a word. */
const PRESENCE_LABEL: Record<Presence, string> = {
  working: "Working",
  waiting: "Waiting for you",
  idle: "Idle",
};

/** The persona being edited: a stored bot, or one not created yet (id null). */
interface Editing {
  id: string | null;
  identity: Identity;
  instructions: string;
}

/** The editor opens on a bot's own words: its persona and its instructions. */
const openOf = (bot: Bot): Editing => ({
  id: bot.id,
  identity: identityOf(bot, DRAGON, AVATAR_COLORS[0]),
  instructions: bot.instructions,
});

/**
 * The bots screen: the roster of personas on the left — each with its face, its line and
 * what it is up to — and the selected bot's own panel on the right: its face, name, voice
 * and instructions, in titled sections. Create one, edit one, delete one. The default bot
 * and the last bot cannot go; the runtime refuses those and its message is shown as it comes.
 */
export function BotsScreen() {
  const { state, dispatch, toast } = useStore();
  const t = useT();
  const ids = useId();
  // the list: the snapshot's bots, kept fresh from the runtime as the screen is used
  const [bots, setBots] = useState<Bot[]>(state.bots);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // what each bot is up to, read off the snapshot the console keeps (threads, approvals, holds)
  const presence: PresenceInput = useMemo(
    () => ({
      threads: state.threads ?? [],
      status: state.status ?? { state: "idle", detail: "", thread: "main" },
      pendingApprovals: state.pendingApprovals ?? [],
      holds: state.holds ?? [],
    }),
    [state.threads, state.status, state.pendingApprovals, state.holds],
  );

  const reload = async () => {
    try {
      const d = await api.bots();
      setBots(d.bots);
      dispatch({ type: "bots", bots: d.bots });
    } catch (e) {
      toast((e as Error).message);
    }
  };

  useEffect(() => {
    void (async () => {
      try {
        const d = await api.bots();
        setBots(d.bots);
        dispatch({ type: "bots", bots: d.bots });
        // a roster with a choice in it opens on its first bot; with only the default bot the
        // panel keeps the invitation to add the next one
        if (d.bots.length > 1) setEditing((e) => e ?? openOf(d.bots[0]));
      } catch (e) {
        toast((e as Error).message);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // at narrow widths the panel sits under the roster and wants to be seen when it opens
  const scrollToPanel = () => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    if (window.matchMedia("(min-width: 64rem)").matches) return;
    requestAnimationFrame(() => panelRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
  };

  const openBot = (bot: Bot) => {
    setError(null);
    setConfirming(false);
    setEditing(openOf(bot));
    scrollToPanel();
  };

  const newBot = () => {
    setError(null);
    setConfirming(false);
    setEditing({
      id: null,
      identity: { name: "", tagline: "", avatar: DRAGON, emoji: "✨", color: AVATAR_COLORS[0], tone: "", communication: "", style: "", user_name: "" },
      instructions: "",
    });
    scrollToPanel();
  };

  const setIdentity = (identity: Identity) => setEditing((e) => (e ? { ...e, identity } : e));

  const body = (e: Editing): Partial<Bot> & { name: string } => {
    const v = identityBody(e.identity);
    return {
      name: v.name,
      avatar: v.avatar,
      emoji: v.emoji,
      color: v.color,
      tagline: v.tagline,
      tone: v.tone,
      communication: v.communication,
      style: v.style,
      instructions: e.instructions.trim(),
    };
  };

  const save = async () => {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      if (editing.id) {
        await api.updateBot(editing.id, body(editing));
      } else {
        const created = await api.createBot(body(editing));
        setEditing({ ...editing, id: created.bot.id });
      }
      await reload();
      toast(t("Saved"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!editing?.id) return;
    setBusy(true);
    setError(null);
    try {
      await api.deleteBot(editing.id);
      setEditing(null);
      await reload();
      toast(t("Deleted"));
    } catch (e) {
      // the runtime's own refusal (the default bot, the last bot): shown as it came
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <PageBar
        title={t("Bots")}
        description={t("Every bot is its own persona, with its own face, voice and job.")}
        actions={
          <button
            type="button"
            onClick={newBot}
            className="flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-1.5 text-[13px] font-semibold text-accent-fg shadow-sm transition active:scale-95"
          >
            <Plus size={15} /> {t("New bot")}
          </button>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-8 wide:overflow-hidden">
        <div className="wide:grid wide:h-full wide:grid-cols-[300px_minmax(0,1fr)] wide:gap-5">
          <aside className="wide:h-full wide:overflow-y-auto wide:pb-6">
            <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2 wide:grid-cols-1">
              {bots.map((bot) => {
                const mood = botMood(bot.id, presence);
                const active = editing?.id === bot.id;
                const tone = toneLabel(bot.tone);
                const comm = commLabel(bot.communication);
                return (
                  <li key={bot.id}>
                    <button
                      type="button"
                      aria-label={bot.name}
                      onClick={() => openBot(bot)}
                      className={cx(
                        "group flex w-full items-center gap-3 rounded-2xl border px-3 py-2.5 text-left transition-all duration-150 active:scale-[0.98]",
                        active
                          ? "border-accent/50 bg-accent-soft/60 shadow-sm"
                          : "border-border/55 bg-surface hover:-translate-y-0.5 hover:border-border hover:shadow-md",
                      )}
                    >
                      <span className="relative">
                        <Avatar profile={bot} mood={mood} size={44} still />
                        <span className={cx("absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-surface", PRESENCE_DOT[mood])} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-1.5">
                          <span className="truncate text-[14px] font-semibold leading-tight">{bot.name}</span>
                          {bot.id === DEFAULT_BOT_ID && (
                            <span className="shrink-0 rounded-full bg-surface-2 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-muted">
                              {t("Default")}
                            </span>
                          )}
                        </span>
                        <span className="mt-0.5 block truncate text-[11.5px] leading-snug text-muted">
                          {bot.tagline || bot.instructions.split("\n")[0] || t(PRESENCE_LABEL[mood])}
                        </span>
                        {(tone || comm) && (
                          <span className="mt-1.5 flex flex-wrap gap-1">
                            {tone && (
                              <span className="rounded-full bg-accent-soft/80 px-2 py-0.5 text-[10px] font-semibold text-accent-soft-fg">{t(tone)}</span>
                            )}
                            {comm && (
                              <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[10px] font-medium text-muted">{t(comm)}</span>
                            )}
                          </span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
              <li>
                <button
                  type="button"
                  onClick={newBot}
                  className="flex h-full w-full items-center gap-3 rounded-2xl border border-dashed border-border/70 px-3 py-2.5 text-left text-muted transition hover:border-accent/50 hover:bg-accent-soft/30 hover:text-accent"
                >
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface-2">
                    <Plus size={18} />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-[13px] font-semibold">{t("New bot")}</span>
                    <span className="block truncate text-[11.5px] opacity-80">{t("Its own face, voice and job.")}</span>
                  </span>
                </button>
              </li>
            </ul>
          </aside>
          <div ref={panelRef} className="mt-5 wide:mt-0 wide:h-full wide:overflow-hidden">
            {editing ? (
              <EditorPanel
                editing={editing}
                bots={bots}
                presence={presence}
                busy={busy}
                error={error}
                confirming={confirming}
                ids={ids}
                onIdentity={setIdentity}
                onInstructions={(instructions) => setEditing((e) => (e ? { ...e, instructions } : e))}
                onSave={() => void save()}
                onDelete={() => setConfirming(true)}
                onConfirmDelete={() => void remove()}
                onKeep={() => setConfirming(false)}
                onCancel={() => setEditing(null)}
              />
            ) : bots.length <= 1 ? (
              <div className="flex min-h-[380px] flex-col items-center justify-center rounded-3xl border border-dashed border-border/70 bg-surface-2/30 px-8 py-12 text-center wide:h-full">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-accent-soft text-accent shadow-sm">
                  <Plus size={22} />
                </div>
                <p className="mt-4 text-[15.5px] font-semibold">
                  {t("Only {name} so far.", { name: defaultBot(bots, state.profile).name })}
                </p>
                <p className="mt-1.5 max-w-[320px] text-[13px] leading-relaxed text-muted">
                  {t("Add another when a job needs its own face and voice.")}
                </p>
                <button
                  type="button"
                  onClick={newBot}
                  className="mt-5 flex items-center gap-1.5 rounded-full bg-accent px-4 py-2 text-[13.5px] font-semibold text-accent-fg shadow-sm transition active:scale-95"
                >
                  <Plus size={15} /> {t("New bot")}
                </button>
              </div>
            ) : (
              <div className="flex min-h-[220px] items-center justify-center rounded-3xl border border-border/50 bg-surface-2/20 px-8 py-10 text-center wide:h-full">
                <p className="max-w-[300px] text-[13px] leading-relaxed text-muted">
                  {t("Select a bot to see its face, voice and instructions.")}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** One titled block of the editor panel. */
function Section({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="py-5">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted">{label}</h3>
      <div className="mt-3">{children}</div>
    </div>
  );
}

/** The selected bot's panel: who it is on top, its face, voice and instructions below. */
function EditorPanel({
  editing,
  bots,
  presence,
  busy,
  error,
  confirming,
  ids,
  onIdentity,
  onInstructions,
  onSave,
  onDelete,
  onConfirmDelete,
  onKeep,
  onCancel,
}: {
  editing: Editing;
  bots: Bot[];
  presence: PresenceInput;
  busy: boolean;
  error: string | null;
  confirming: boolean;
  ids: string;
  onIdentity: (identity: Identity) => void;
  onInstructions: (instructions: string) => void;
  onSave: () => void;
  onDelete: () => void;
  onConfirmDelete: () => void;
  onKeep: () => void;
  onCancel: () => void;
}) {
  const t = useT();
  const draft = editing.id === null;
  const named = editing.identity.name.trim().length > 0;
  const stored = editing.id ? bots.find((b) => b.id === editing.id) : null;
  const mood: Presence = editing.id ? botMood(editing.id, presence) : "idle";
  const tone = toneLabel(editing.identity.tone);
  const comm = commLabel(editing.identity.communication);
  // the face, the name and the line follow the form as it is typed
  const preview: Bot = {
    id: editing.id ?? "draft",
    name: editing.identity.name,
    avatar: editing.identity.avatar,
    emoji: editing.identity.emoji,
    color: editing.identity.color,
    tagline: editing.identity.tagline,
    tone: editing.identity.tone,
    communication: editing.identity.communication,
    style: editing.identity.style,
    instructions: editing.instructions,
    model: "",
    created_at: 0,
  };
  const heading = editing.identity.name.trim() || t("New bot");
  const sub = editing.identity.tagline.trim() || editing.instructions.trim().split("\n")[0];

  return (
    <section className="overflow-hidden rounded-3xl border border-border/60 bg-surface shadow-sm wide:flex wide:h-full wide:flex-col">
      <header className="relative shrink-0 overflow-hidden px-5 pb-5 pt-5">
        <div aria-hidden className="absolute inset-0 bg-gradient-to-br from-accent-soft via-accent-soft/30 to-transparent" />
        <div className="relative flex items-center gap-4">
          <div className="rounded-full bg-surface/60 p-1 shadow-sm ring-1 ring-border/40">
            <Avatar
              profile={preview}
              size={84}
              mood={draft ? undefined : mood}
              status={draft ? undefined : { state: mood, detail: "", thread: "" }}
            />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-[20px] font-bold leading-tight tracking-tight">{heading}</h2>
            {sub && <p className="mt-1 truncate text-[13px] text-muted">{sub}</p>}
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              {!draft && (
                <span className="inline-flex items-center gap-1.5 rounded-full border border-border/50 bg-surface/70 px-2.5 py-1 text-[11px] font-medium text-muted">
                  <span className={cx("h-2 w-2 rounded-full", PRESENCE_DOT[mood])} />
                  {t(PRESENCE_LABEL[mood])}
                </span>
              )}
              {stored?.id === DEFAULT_BOT_ID && (
                <span className="rounded-full border border-border/50 bg-surface/70 px-2.5 py-1 text-[11px] font-medium text-muted">
                  {t("Default")}
                </span>
              )}
              {tone && (
                <span className="rounded-full bg-accent-soft px-2.5 py-1 text-[11px] font-semibold text-accent-soft-fg">{t(tone)}</span>
              )}
              {comm && (
                <span className="rounded-full border border-border/50 bg-surface/70 px-2.5 py-1 text-[11px] font-medium text-muted">{t(comm)}</span>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="divide-y divide-border/50 px-5 wide:min-h-0 wide:flex-1 wide:overflow-y-auto">
        <Section label={t("Who it is")}>
          <IdentityNameFields
            value={editing.identity}
            onChange={onIdentity}
            suggestions={draft}
            inputCls={botInput}
          />
        </Section>
        <Section label={t("Face")}>
          <AvatarPicker
            value={{ avatar: editing.identity.avatar, emoji: editing.identity.emoji, color: editing.identity.color }}
            onChange={(look) => onIdentity({ ...editing.identity, ...look })}
          />
          <p className="mt-2.5 text-[12px] leading-snug text-muted">{t("The face it wears in the roster and the chats.")}</p>
        </Section>
        <Section label={t("Voice")}>
          <IdentityVoice value={editing.identity} onChange={onIdentity} inputCls={botInput} />
        </Section>
        <Section label={t("Instructions")}>
          <textarea
            id={`${ids}-instructions`}
            aria-label={t("Instructions")}
            value={editing.instructions}
            onChange={(ev) => onInstructions(ev.target.value)}
            rows={5}
            placeholder={t("What this bot is for, and how it should do it.")}
            className={cx(botInput, "resize-none text-[14px] leading-relaxed")}
          />
        </Section>
      </div>

      {error && (
        <div className="shrink-0 px-5 pb-3">
          <p role="alert" className="rounded-2xl bg-rose-500/10 px-3.5 py-2.5 text-[13px] leading-snug text-rose-600 dark:text-rose-300">
            {error}
          </p>
        </div>
      )}
      {editing.id && confirming && (
        <div className="flex shrink-0 items-center gap-2 border-t border-rose-500/25 bg-rose-500/10 px-5 py-3">
          <span className="min-w-0 flex-1 text-[13px]">{t("Delete this bot?")}</span>
          <button
            type="button"
            disabled={busy}
            onClick={onConfirmDelete}
            className="rounded-full bg-rose-500 px-3.5 py-1.5 text-[12.5px] font-semibold text-white transition disabled:opacity-50"
          >
            {t("Delete")}
          </button>
          <button type="button" onClick={onKeep} className="rounded-full px-3 py-1.5 text-[12.5px] text-muted transition hover:text-fg">
            {t("Keep")}
          </button>
        </div>
      )}
      <footer className="flex shrink-0 items-center gap-2 border-t border-border/60 bg-surface-2/40 px-5 py-3.5">
        {editing.id && !confirming && (
          <button
            type="button"
            onClick={onDelete}
            className="flex items-center gap-1.5 rounded-full px-3 py-2 text-[13px] font-medium text-rose-600 transition hover:bg-rose-500/10 dark:text-rose-300"
          >
            <Trash2 size={15} /> {t("Delete bot")}
          </button>
        )}
        <div className="flex-1" />
        {draft && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-border px-4 py-2 text-[13px] font-medium text-muted transition hover:bg-surface-2 hover:text-fg"
          >
            {t("Cancel")}
          </button>
        )}
        <button
          type="button"
          disabled={busy || (draft && !named)}
          onClick={onSave}
          className="flex items-center gap-1.5 rounded-full bg-accent px-5 py-2 text-[13.5px] font-semibold text-accent-fg shadow-sm transition disabled:opacity-40 active:scale-[0.98]"
        >
          {busy ? <Loader2 size={15} className="animate-spin" /> : editing.id ? <Check size={15} /> : <Plus size={15} />}
          {editing.id ? t("Save") : t("Create")}
        </button>
      </footer>
    </section>
  );
}
