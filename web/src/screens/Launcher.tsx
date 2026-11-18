import { Bot, FileText, Home, MessageSquare, Search, Settings, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { isChief } from "../bots";
import { useT } from "../i18n";
import { useStore, type Tab } from "../store";
import { cx } from "../util";
import { Avatar } from "../components/Avatar";
import { useFocusTrap } from "../components/useFocusTrap";

/**
 * The command bar (⌘K / Ctrl+K): one input over the page, answers grouped —
 * Settings sections to jump to, chats to open, bots to open, and a
 * "remember …" line that writes a memory without opening the Memory page.
 * Raycast's shape: anchored top, one input, Escape out, Enter on the first hit.
 * The launcher only opens from the keyboard; a phone has no ⌘K gesture, and the
 * chats drawer and the tab bar are the way around there.
 */

interface Row {
  id: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  group: string;
  /** what the row does; only ever called from a click or Enter, never during render */
  run: (actions: RowActions) => void;
}

/** The actions a row's run() may take, passed at the call site so the memo stays pure. */
interface RowActions {
  close: () => void;
  setTab: (tab: Tab) => void;
  openThread: (thread: string) => void;
  remember: (text: string) => void;
}

export function Launcher({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { state, setTab, openThread, toast } = useStore();
  const t = useT();
  const [query, setQuery] = useState("");
  const [at, setAt] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  useFocusTrap(panel, open);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setAt(0);
    requestAnimationFrame(() => input.current?.focus());
  }, [open]);

  const close = () => {
    onClose();
    // focus returns to the page; the keydown that opened us must not type into it
    input.current?.blur();
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const name = state.profile?.name ?? "Dragon";

  const actions = useMemo<RowActions>(
    () => ({
      close,
      setTab,
      openThread,
      remember: (text: string) => {
        api
          .addMemory(text, "general")
          .then(() => toast(t("Remembered")))
          .catch((e: Error) => toast(e.message));
      },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setTab, openThread, t],
  );

  const rows = useMemo<Row[]>(() => {
    const q = query.trim().toLowerCase();
    const hit = (s: string) => !q || s.toLowerCase().includes(q);
    const out: Row[] = [];
    // remember: writes a memory straight away ("remember: my dentist is …")
    const note = query.trim().replace(/^(remember|note|记[住着])[:：]?\s*/i, "");
    if (note) {
      out.push({
        id: "remember",
        label: t("Remember: {text}", { text: note }),
        hint: t("Memory"),
        icon: <Sparkles size={16} className="text-accent" />,
        group: t("Memory"),
        run: (a) => {
          a.remember(note);
          a.close();
        },
      });
    }
    const settings: Array<{ id: Tab; label: string; icon: ReactNode }> = [
      { id: "you", label: t("Settings"), icon: <Settings size={16} /> },
      { id: "connections", label: t("Connections"), icon: <Search size={16} /> },
      { id: "memory", label: t("Memory"), icon: <FileText size={16} /> },
      { id: "skills", label: t("Skills"), icon: <Sparkles size={16} /> },
      { id: "channels", label: t("Chat apps"), icon: <MessageSquare size={16} /> },
      { id: "coding", label: t("Coding agents"), icon: <Bot size={16} /> },
      { id: "avatar", label: t("Avatar studio"), icon: <Sparkles size={16} /> },
      { id: "bots", label: t("Bots"), icon: <Bot size={16} /> },
    ];
    for (const s of settings) {
      if (!hit(s.label)) continue;
      out.push({
        id: `tab:${s.id}`,
        label: s.label,
        hint: t("Settings"),
        icon: s.icon,
        group: t("Settings"),
        run: (a) => {
          a.setTab(s.id);
          a.close();
        },
      });
    }
    if (hit(t("Main chat")) || hit(name)) {
      out.push({
        id: "thread:main",
        label: t("Main chat"),
        hint: name,
        icon: <Home size={16} />,
        group: t("Chats"),
        run: (a) => {
          a.openThread("main");
          a.close();
        },
      });
    }
    for (const th of state.threads) {
      if (th.id === "main") continue;
      if (!hit(th.title || "")) continue;
      out.push({
        id: `thread:${th.id}`,
        label: th.title || t("New chat"),
        hint: t("{n} events", { n: th.events }),
        icon: <MessageSquare size={16} />,
        group: t("Chats"),
        run: (a) => {
          a.openThread(th.id);
          a.close();
        },
      });
    }
    for (const bot of state.bots) {
      if (isChief(bot)) continue;
      if (!hit(bot.name) && !hit(bot.tagline || "")) continue;
      out.push({
        id: `bot:${bot.id}`,
        label: bot.name,
        hint: bot.tagline || undefined,
        icon: <Avatar profile={bot} size={20} still />,
        group: t("Bots"),
        run: (a) => {
          a.setTab("bots");
          a.close();
        },
      });
    }
    return out;
  }, [query, state.threads, state.bots, name, t]);

  // Enter on the first hit; the arrows walk.
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setAt((v) => Math.min(v + 1, Math.max(0, rows.length - 1)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setAt((v) => Math.max(0, v - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      rows[at]?.run(actions);
    }
  };

  if (!open) return null;

  // The groups, in the order the rows were built.
  const groups: Array<{ label: string; rows: Row[] }> = [];
  for (const row of rows) {
    const g = groups.find((x) => x.label === row.group);
    if (g) g.rows.push(row);
    else groups.push({ label: row.group, rows: [row] });
  }
  let index = -1;

  return (
    <div className="fixed inset-0 z-[60]">
      <div className="absolute inset-0 bg-black/45 backdrop-blur-[2px]" onClick={close} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={t("Quick launcher")}
        className="rise mx-auto mt-[12vh] flex w-[calc(100%-32px)] max-w-[560px] flex-col overflow-hidden rounded-3xl border border-border bg-surface shadow-lg"
      >
        <div className="flex items-center gap-2.5 border-b border-border/60 px-4 py-3">
          <Search size={17} className="shrink-0 text-muted" />
          <input
            ref={input}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setAt(0);
            }}
            onKeyDown={onKey}
            placeholder={t("Type a command, a setting or a chat name")}
            aria-label={t("Quick launcher")}
            className="min-w-0 flex-1 bg-transparent text-[15px] outline-none placeholder:text-muted"
          />
          <button type="button" onClick={close} aria-label={t("Close")} className="shrink-0 rounded-full p-1.5 text-muted hover:bg-surface-2">
            <X size={16} />
          </button>
        </div>
        <div className="max-h-[52vh] overflow-y-auto py-1.5">
          {rows.length === 0 && <div className="px-4 py-6 text-center text-[13.5px] text-muted">{t("Nothing matches")}</div>}
          {groups.map((g) => (
            <div key={g.label}>
              <div className="px-4 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{g.label}</div>
              {g.rows.map((row) => {
                index += 1;
                const active = index === at;
                return (
                  <button
                    key={row.id}
                    type="button"
                    onMouseEnter={() => setAt(index)}
                    onClick={() => row.run(actions)}
                    className={cx(
                      "flex w-full items-center gap-2.5 px-4 py-2.5 text-left text-[14px]",
                      active && "bg-accent-soft/70",
                    )}
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center text-muted">{row.icon}</span>
                    <span className="min-w-0 flex-1 truncate">{row.label}</span>
                    {row.hint && <span className="shrink-0 text-[11.5px] text-muted">{row.hint}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
