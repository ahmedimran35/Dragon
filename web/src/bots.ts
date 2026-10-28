/**
 * The bots: the personas the person chats with. One of them is the default — the id
 * exactly "default" — and every chat falls back to it: a chat from before bots, a thread
 * whose bot is gone, a runtime that sends no list at all. Presence is read off the state
 * snapshot the console already keeps: a bot is working when one of its chats is busy,
 * waiting when an approval or a hold stands on one of them, idle otherwise.
 */

import type { Mood } from "./mood";
import type { ApprovalEvent, Bot, HoldEvent, Profile, Status, ThreadMeta } from "./types";

/** The bot every chat falls back to. */
export const DEFAULT_BOT_ID = "default";

/** What a bot's presence is read from: the parts of the state snapshot that say so. */
export interface PresenceInput {
  threads: ThreadMeta[];
  status: Status;
  pendingApprovals: ApprovalEvent[];
  holds?: HoldEvent[];
}

/** A bot's presence: the avatar moods that stand for a state, not for a moment. */
export type Presence = Extract<Mood, "idle" | "working" | "waiting">;

/** The bot a thread is with: the one its meta names, else the default bot. */
export function botIdOfThread(thread: Pick<ThreadMeta, "bot_id"> | null | undefined): string {
  return thread?.bot_id || DEFAULT_BOT_ID;
}

/**
 * The chief of staff: the bot that manages the roster and briefs the others. The runtime
 * marks it with `role: "chief"`; on a runtime from before roles the id "default" is the
 * mark. Every other bot is staff, and each staff bot has one chat of its own.
 */
export function isChief(bot: Pick<Bot, "id" | "role"> | null | undefined): boolean {
  return !!bot && (bot.role === "chief" || bot.id === DEFAULT_BOT_ID);
}

/**
 * The default bot when the runtime sent none: the stand-in wears the runtime profile's
 * name and face, the way older runtimes showed one agent. `created_at` 0 marks it as
 * not a stored bot.
 */
export function fallbackBot(profile?: Partial<Profile> | null): Bot {
  return {
    id: DEFAULT_BOT_ID,
    name: profile?.name ?? "Ember",
    avatar: profile?.avatar ?? "dragon",
    emoji: profile?.emoji ?? "",
    color: profile?.color ?? "",
    tagline: profile?.tagline ?? "",
    tone: profile?.tone ?? "",
    communication: profile?.communication ?? "",
    style: profile?.style ?? "",
    instructions: "",
    model: "",
    created_at: 0,
  };
}

/** The default bot: the one with the id "default", else the first, else the stand-in. */
export function defaultBot(bots: Bot[] | null | undefined, profile?: Partial<Profile> | null): Bot {
  return bots?.find((b) => b.id === DEFAULT_BOT_ID) ?? bots?.[0] ?? fallbackBot(profile);
}

/** The bot a chat is with: the one its meta names when that bot exists, else the default bot. */
export function botForThread(bots: Bot[] | null | undefined, thread: Pick<ThreadMeta, "bot_id"> | null | undefined, profile?: Partial<Profile> | null): Bot {
  const id = botIdOfThread(thread);
  return bots?.find((b) => b.id === id) ?? defaultBot(bots, profile);
}

/**
 * What a bot's face shows, as one of the avatar's moods: "working" while one of its chats
 * is busy (or the live status stands on one), "waiting" while an approval or a hold needs
 * the person on one of them, "idle" otherwise. "happy" and "error" are moments of this
 * session's own (a run ending well, a call failing); the snapshot carries no per-bot
 * signal for them, so a bot at rest shows idle.
 */
export function botMood(botId: string, snapshot: PresenceInput): Presence {
  const owner = (thread: string) => botIdOfThread(snapshot.threads.find((t) => t.id === thread));
  if (snapshot.threads.some((t) => botIdOfThread(t) === botId && t.busy)) return "working";
  if (snapshot.status.state === "working" && owner(snapshot.status.thread) === botId) return "working";
  if (snapshot.pendingApprovals.some((a) => owner(a.thread) === botId)) return "waiting";
  if ((snapshot.holds ?? []).some((h) => h.status === "on" && owner(h.thread) === botId)) return "waiting";
  return "idle";
}
