import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Avatar } from "./Avatar";
import { BotRoster } from "./BotRoster";
import { setLocaleSetting } from "../i18n";
import type { ApprovalEvent, Bot, ThreadMeta } from "../types";

// Avatar follows the mood it is given; its fallback mood hook reads the store
vi.mock("../store", () => ({
  useStore: () => ({ state: { loaded: true, connected: true, mishapAt: 0, finishedAt: 0 } }),
}));

const ember: Bot = {
  id: "default",
  name: "Ember",
  avatar: "dragon",
  emoji: "",
  color: "",
  tagline: "",
  tone: "",
  communication: "",
  style: "",
  instructions: "",
  model: "",
  created_at: 1761000000,
};

const sage: Bot = {
  ...ember,
  id: "b_9f3ab2c1",
  name: "Sage",
  avatar: "",
  emoji: "🌿",
  color: "#059669",
  tagline: "Slow, careful answers",
};

const meta = (id: string, bot_id: string, busy = false): ThreadMeta => ({
  id,
  title: id,
  created_at: "2026-10-28T08:00:00Z",
  updated_at: "2026-10-28T09:00:00Z",
  busy,
  queued: 0,
  events: 1,
  bot_id,
});

const approval = (thread: string): ApprovalEvent => ({
  id: "approval-1",
  ts: "2026-10-28T09:00:00Z",
  thread,
  type: "approval",
  tool: "shell",
  summary: "",
  risk: "sensitive",
  reasons: [],
  warnings: [],
  args: {},
  status: "pending",
});

let screen: ReactTestRenderer;

function renderedText(): string {
  const walk = (node: unknown): string => {
    if (typeof node === "string") return node;
    if (Array.isArray(node)) return node.map(walk).join(" ");
    if (node && typeof node === "object" && "children" in node) {
      return walk((node as { children: unknown }).children);
    }
    return "";
  };
  return walk(screen.toJSON());
}

function moods(): string[] {
  return screen.root.findAllByType(Avatar).map((a) => String(a.props.mood));
}

afterEach(() => {
  if (screen) act(() => screen.unmount());
  setLocaleSetting("en");
  vi.restoreAllMocks();
});

describe("BotRoster", () => {
  it("shows one row per bot with its name and face", async () => {
    setLocaleSetting("en");
    await act(async () => {
      screen = create(
        createElement(BotRoster, {
          bots: [ember, sage],
          presence: { threads: [], status: { state: "idle", detail: "", thread: "main" }, pendingApprovals: [] },
          onPick: () => undefined,
        }),
      );
    });
    const text = renderedText();
    expect(text).toContain("Ember");
    expect(text).toContain("Sage");
    expect(text).toContain("Slow, careful answers");
  });

  it("shows what each bot is up to: working, waiting, and idle as the fallback", async () => {
    setLocaleSetting("en");
    await act(async () => {
      screen = create(
        createElement(BotRoster, {
          bots: [ember, sage],
          presence: {
            // the default bot works on its own chat; an approval waits on Sage's chat
            threads: [meta("main", "default", true), meta("sage-chat", sage.id)],
            status: { state: "idle", detail: "", thread: "main" },
            pendingApprovals: [approval("sage-chat")],
            holds: [],
          },
          onPick: () => undefined,
        }),
      );
    });
    expect(moods()).toEqual(["working", "waiting"]);
  });

  it("falls back to idle when the snapshot says nothing about a bot", async () => {
    setLocaleSetting("en");
    await act(async () => {
      screen = create(
        createElement(BotRoster, {
          bots: [ember, sage],
          presence: {
            threads: [meta("sage-chat", sage.id)],
            status: { state: "idle", detail: "", thread: "main" },
            pendingApprovals: [],
            holds: [],
          },
          onPick: () => undefined,
        }),
      );
    });
    expect(moods()).toEqual(["idle", "idle"]);
  });

  it("offers a row tap with the bot it starts a chat with", async () => {
    const onPick = vi.fn();
    setLocaleSetting("en");
    await act(async () => {
      screen = create(
        createElement(BotRoster, {
          bots: [ember, sage],
          presence: { threads: [], status: { state: "idle", detail: "", thread: "main" }, pendingApprovals: [] },
          onPick,
        }),
      );
    });
    await act(async () => {
      screen.root.findAllByType("button")[1]?.props.onClick();
    });
    expect(onPick).toHaveBeenCalledWith(sage);
  });
});
