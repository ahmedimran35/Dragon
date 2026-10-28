import { botMood, isChief, type PresenceInput } from "../bots";
import { useT } from "../i18n";
import type { Bot } from "../types";
import { cx } from "../util";
import { Avatar } from "./Avatar";
import { ChiefBadge } from "./ChiefBadge";

/**
 * The bot roster: one row per bot — its face, its name and its line — with the face showing
 * what that bot is up to (working on one of its chats, waiting on an approval or a hold; idle
 * otherwise). A row opens that bot's chat: the staff bot's own single chat, a new chat with
 * the chief. The chief carries the chief-of-staff mark.
 */
export function BotRoster({
  bots,
  presence,
  onPick,
  className,
}: {
  bots: Bot[];
  /** the snapshot presence is read from (threads, status, approvals, holds) */
  presence: PresenceInput;
  onPick: (bot: Bot) => void;
  className?: string;
}) {
  const t = useT();
  return (
    <ul aria-label={t("Bots")} className={cx("space-y-1", className)}>
      {bots.map((bot) => {
        const mood = botMood(bot.id, presence);
        return (
          <li key={bot.id}>
            <button
              type="button"
              onClick={() => onPick(bot)}
              className="flex w-full items-center gap-2.5 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-surface-2/70 active:scale-[0.99]"
            >
              <Avatar profile={bot} mood={mood} status={{ state: mood, detail: "", thread: "" }} size={32} still />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold leading-tight">{bot.name}</span>
                {(isChief(bot) || bot.tagline) && (
                  <span className="mt-0.5 flex items-center gap-1.5">
                    {isChief(bot) && <ChiefBadge compact />}
                    {bot.tagline && <span className="min-w-0 truncate text-[11px] leading-tight text-muted">{bot.tagline}</span>}
                  </span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
