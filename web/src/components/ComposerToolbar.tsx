import { AtSign } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "../api";
import { isChief } from "../bots";
import { useT } from "../i18n";
import { useStore } from "../store";
import type { Bot, ThreadMeta } from "../types";
import { cx } from "../util";
import { Avatar } from "./Avatar";
import { ChiefBadge } from "./ChiefBadge";
import { useFocusTrap } from "./useFocusTrap";

/**
 * The composer's chip row: one chip, `@bot`, that opens the roster as a small popover
 * above the composer. Picking the chief keeps this chat; picking a staff bot opens that
 * bot's own chat (a staff bot has exactly one) — the same jump the roster on the Bots
 * page does, one tap closer. The row hides when there is nobody to switch to.
 */
export function ComposerToolbar({ disabled }: { disabled?: boolean }) {
  const { state, dispatch, openThread, toast } = useStore();
  const t = useT();
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  useFocusTrap(panel, open);

  const staff = (state.bots ?? []).filter((b) => !isChief(b));
  const chief = (state.bots ?? []).find((b) => isChief(b));
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: PointerEvent) => {
      if (!wrap.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  const chatWith = async (bot: Bot) => {
    setOpen(false);
    if (isChief(bot)) {
      openThread("main");
      return;
    }
    try {
      const thread: ThreadMeta = await api.createThread(bot.name || t("New chat"), bot.id);
      dispatch({ type: "ws", msg: { kind: "thread", thread } });
      openThread(thread.id);
    } catch (e) {
      toast((e as Error).message);
    }
  };

  // nothing to offer until the roster has arrived with a second persona on it
  if (staff.length === 0 && !chief) return null;

  return (
    <div ref={wrap} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={t("Chat with another bot")}
        className="flex h-7 shrink-0 items-center gap-1.5 rounded-full border border-border/70 bg-surface-2/70 px-2.5 text-[12.5px] font-medium text-fg/80 transition hover:bg-surface-2 active:scale-95 disabled:opacity-50"
      >
        <AtSign size={13} className="text-accent" />
        {t("bot")}
      </button>
      {open && (
        <div
          ref={panel}
          role="dialog"
          aria-label={t("Bots")}
          className="rise absolute bottom-9 left-0 z-30 w-64 overflow-hidden rounded-2xl border border-border bg-surface py-1 shadow-lg"
        >
          {chief && (
            <PopoverRow bot={chief} onClick={() => void chatWith(chief)}>
              <ChiefBadge compact />
            </PopoverRow>
          )}
          {staff.map((bot) => (
            <PopoverRow key={bot.id} bot={bot} onClick={() => void chatWith(bot)} />
          ))}
          {state.bots.length === 0 && (
            <div className="flex items-center gap-2 px-3 py-2.5 text-[13px] text-muted">
              <AtSign size={16} /> {t("One bot so far — the chief of staff.")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PopoverRow({ bot, onClick, children }: { bot: Bot; onClick: () => void; children?: ReactNode }) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx("flex w-full items-center gap-2.5 px-3 py-2 text-left transition-colors hover:bg-surface-2/70")}
      aria-label={t("Chat with {name}", { name: bot.name })}
    >
      <Avatar profile={bot} size={28} still />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-semibold leading-tight">{bot.name}</span>
        {bot.tagline && <span className="block truncate text-[11px] leading-tight text-muted">{bot.tagline}</span>}
      </span>
      {children}
    </button>
  );
}
