import { useT } from "../i18n";
import type { Bot } from "../types";
import { cx } from "../util";
import { Avatar } from "./Avatar";

/**
 * Which bot a new chat is with: a row of faces with their names, the chosen one on the pale
 * gold. It stays out of the way when there is only one bot — then there is nothing to pick.
 */
export function BotPicker({ bots, value, onChange }: { bots: Bot[]; value: string; onChange: (id: string) => void }) {
  const t = useT();
  if (bots.length < 2) return null;
  return (
    <div role="radiogroup" aria-label={t("Bot for the new chat")} className="mb-2 flex gap-1.5 overflow-x-auto px-0.5 pb-0.5">
      {bots.map((bot) => (
        <button
          key={bot.id}
          type="button"
          role="radio"
          aria-checked={value === bot.id}
          onClick={() => onChange(bot.id)}
          className={cx(
            "flex shrink-0 items-center gap-1.5 rounded-full border py-1 pl-1 pr-3 text-[12px] transition-all active:scale-[0.98]",
            value === bot.id
              ? "border-accent/30 bg-accent-soft font-semibold text-accent-soft-fg shadow-sm"
              : "border-border/55 bg-surface text-muted hover:border-border hover:text-fg",
          )}
        >
          <Avatar profile={bot} size={22} still />
          <span className="max-w-[110px] truncate">{bot.name}</span>
        </button>
      ))}
    </div>
  );
}
