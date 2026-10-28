import { describe, expect, it } from "vitest";
import { botForThread, botIdOfThread, botMood, defaultBot, DEFAULT_BOT_ID, type PresenceInput } from "./bots";
import type { ApprovalEvent, Bot, HoldEvent, Profile, StateSnapshot, ThreadMeta } from "./types";

const profile: Profile = {
  name: "Ember",
  avatar: "dragon",
  emoji: "",
  color: "",
  tagline: "",
  tone: "",
  communication: "",
  style: "",
  user_name: "",
  proactivity: "default",
  proactive: true,
  goal_interval_minutes: 60,
  quiet_hours: "",
};

const ember: Bot = {
  id: "default",
  name: "Ember",
  avatar: "dragon",
  emoji: "",
  color: "",
  tagline: "",
  tone: "warm",
  communication: "",
  style: "",
  instructions: "",
  model: "",
  created_at: 1761000000,
};

const sage: Bot = {
  id: "b_9f3ab2c1",
  name: "Sage",
  avatar: "",
  emoji: "🌿",
  color: "#059669",
  tagline: "Slow, careful answers",
  tone: "concise",
  communication: "short",
  style: "",
  instructions: "Answers in short, careful sentences.",
  model: "",
  created_at: 1761000100,
};

const meta = (id: string, bot_id: string, busy = false): ThreadMeta => ({
  id,
  title: id,
  created_at: "2026-10-28T08:00:00Z",
  updated_at: "2026-10-28T09:00:00Z",
  busy,
  queued: 0,
  events: 3,
  bot_id,
});

const approval = (thread: string): ApprovalEvent => ({
  id: "approval-1",
  ts: "2026-10-28T09:00:00Z",
  thread,
  type: "approval",
  tool: "shell",
  summary: "run rm",
  risk: "sensitive",
  reasons: [],
  warnings: [],
  args: {},
  status: "pending",
});

const hold = (thread: string, status: "on" | "off"): HoldEvent => ({
  id: "hold-1",
  // a hold's ts is seconds since the epoch on the wire (contract C1); the store makes it ISO
  ts: 1761000200 as unknown as string,
  thread,
  type: "hold",
  tool: "browser",
  status,
  by: "agent",
  reason: "sign in",
});

const idle = (overrides: Partial<PresenceInput> = {}): PresenceInput => ({
  threads: [],
  status: { state: "idle", detail: "", thread: "main" },
  pendingApprovals: [],
  holds: [],
  ...overrides,
});

describe("bots in the state snapshot", () => {
  it("consumes the bots and the bot of each thread the snapshot carries", () => {
    const snapshot: StateSnapshot = {
      version: "0.0.test",
      profile,
      status: { state: "idle", detail: "", thread: "main" },
      threads: [meta("main", DEFAULT_BOT_ID), meta("sage-chat", sage.id, true)],
      bots: [ember, sage],
      pending_approvals: [],
      goals: [],
      settings: { version: "0.0.test", profile } as StateSnapshot["settings"],
    };
    expect(snapshot.bots.map((b) => b.id)).toEqual([DEFAULT_BOT_ID, "b_9f3ab2c1"]);
    expect(snapshot.threads[1]?.bot_id).toBe("b_9f3ab2c1");
  });

  it("finds the default bot by its id", () => {
    expect(defaultBot([sage, ember]).id).toBe(DEFAULT_BOT_ID);
    // a list without one: the first bot stands in
    expect(defaultBot([sage]).id).toBe(sage.id);
    // no list at all (an older runtime): the stand-in wears the profile's name and face
    const stand = defaultBot([], profile);
    expect(stand.id).toBe(DEFAULT_BOT_ID);
    expect(stand.name).toBe("Ember");
    expect(stand.avatar).toBe("dragon");
    expect(defaultBot(null).name).toBe("Ember");
  });

  it("reads a thread's bot, falling back to the default bot", () => {
    expect(botIdOfThread(meta("sage-chat", sage.id))).toBe("b_9f3ab2c1");
    expect(botIdOfThread(meta("old-chat", ""))).toBe(DEFAULT_BOT_ID);
    expect(botIdOfThread(undefined)).toBe(DEFAULT_BOT_ID);
    expect(botForThread([ember, sage], meta("sage-chat", sage.id)).name).toBe("Sage");
    // a chat whose bot is gone: the default bot
    expect(botForThread([ember], meta("gone", "b_00000000")).id).toBe(DEFAULT_BOT_ID);
    expect(botForThread([], meta("old-chat", ""), profile).name).toBe("Ember");
  });
});

describe("bot presence", () => {
  it("is working while one of the bot's chats is busy", () => {
    const mood = botMood(sage.id, idle({ threads: [meta("main", DEFAULT_BOT_ID), meta("sage-chat", sage.id, true)] }));
    expect(mood).toBe("working");
    expect(botMood(ember.id, idle({ threads: [meta("main", DEFAULT_BOT_ID), meta("sage-chat", sage.id, true)] }))).toBe("idle");
  });

  it("is working while the live status stands on one of its chats", () => {
    const snapshot = idle({
      threads: [meta("sage-chat", sage.id)],
      status: { state: "working", detail: "", thread: "sage-chat" },
    });
    expect(botMood(sage.id, snapshot)).toBe("working");
    expect(botMood(ember.id, snapshot)).toBe("idle");
  });

  it("is waiting while an approval or a hold stands on one of its chats", () => {
    expect(botMood(sage.id, idle({ threads: [meta("sage-chat", sage.id)], pendingApprovals: [approval("sage-chat")] }))).toBe("waiting");
    expect(botMood(sage.id, idle({ threads: [meta("sage-chat", sage.id)], holds: [hold("sage-chat", "on")] }))).toBe("waiting");
    // a hold that is off is no hold
    expect(botMood(sage.id, idle({ threads: [meta("sage-chat", sage.id)], holds: [hold("sage-chat", "off")] }))).toBe("idle");
  });

  it("falls back to idle when nothing says otherwise", () => {
    expect(botMood(ember.id, idle())).toBe("idle");
  });

  it("counts chats that name no bot as the default bot's", () => {
    expect(botMood(DEFAULT_BOT_ID, idle({ threads: [meta("old-chat", "", true)] }))).toBe("working");
    // a thread the list does not carry (the main chat on a quiet load): the default bot's
    expect(botMood(DEFAULT_BOT_ID, idle({ status: { state: "working", detail: "", thread: "main" } }))).toBe("working");
  });
});
