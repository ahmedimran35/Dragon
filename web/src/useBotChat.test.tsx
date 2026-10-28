import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Bot, ThreadMeta } from "./types";
import { setLocaleSetting } from "./i18n";
import { BotRoster } from "./components/BotRoster";
import { useBotChat } from "./useBotChat";

const toast = vi.fn();
const dispatch = vi.fn();
const openThread = vi.fn();

// the hook and the avatar inside the roster both read the store
vi.mock("./store", () => ({
  useStore: () => ({
    state: {
      threads: [],
      bots: [ember, sage],
      activeThread: "main",
      profile: null,
      loaded: true,
      connected: true,
      mishapAt: 0,
      finishedAt: 0,
    },
    dispatch,
    openThread,
    toast,
  }),
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
  role: "chief",
};

const sage: Bot = { ...ember, id: "b_9f3ab2c1", name: "Sage", avatar: "", emoji: "🌿", color: "#059669", role: "staff" };

const sageThread: ThreadMeta = {
  id: "sage-1",
  title: "Sage",
  created_at: "2026-10-28T09:00:00Z",
  updated_at: "2026-10-28T09:00:00Z",
  busy: false,
  queued: 0,
  events: 2,
  bot_id: sage.id,
};

const calls: Array<{ url: string; method: string; body: Record<string, unknown> | null }> = [];

beforeEach(() => {
  calls.length = 0;
  toast.mockClear();
  dispatch.mockClear();
  openThread.mockClear();
  const location = { protocol: "http:", host: "localhost", href: "http://localhost/" };
  vi.stubGlobal("window", { location, setTimeout, clearTimeout, history: { replaceState: () => undefined } });
  vi.stubGlobal("location", location);
  vi.stubGlobal("localStorage", { getItem: () => null, setItem: () => undefined, removeItem: () => undefined });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string | URL, init?: RequestInit) => {
      calls.push({
        url: String(url),
        method: init?.method ?? "GET",
        body: init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null,
      });
      return { ok: true, status: 200, json: async () => sageThread };
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  setLocaleSetting("en");
});

/** The sidebar's wiring: the roster's rows open the bot's chat. */
function Probe() {
  const openBotChat = useBotChat();
  return createElement(BotRoster, {
    bots: [ember, sage],
    presence: { threads: [], status: { state: "idle", detail: "", thread: "main" }, pendingApprovals: [] },
    onPick: (bot: Bot) => void openBotChat(bot),
  });
}

function textOf(node: unknown): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textOf).join(" ");
  if (node && typeof node === "object" && "children" in node) {
    return textOf((node as { children: unknown }).children);
  }
  return "";
}

async function clickRow(screen: ReactTestRenderer, name: string) {
  const row = screen.root.findAllByType("button").find((b) => textOf(b).includes(name));
  expect(row).toBeDefined();
  await act(async () => {
    row?.props.onClick();
  });
}

describe("clicking a staff bot on the roster", () => {
  beforeEach(() => setLocaleSetting("en"));

  it("asks for its one chat with its bot id, then lands on the chat that comes back", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(Probe));
    });
    await clickRow(screen, "Sage");
    const post = calls.find((c) => c.url === "/api/threads" && c.method === "POST");
    expect(post).toBeDefined();
    expect(post?.body).toEqual({ title: "Sage", bot_id: sage.id });
    expect(openThread).toHaveBeenCalledWith("sage-1");
    expect(dispatch).toHaveBeenCalledWith({ type: "ws", msg: { kind: "thread", thread: sageThread } });
  });

  it("opens a fresh chat when the row tapped is the chief's", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(Probe));
    });
    await clickRow(screen, "Ember");
    const post = calls.find((c) => c.url === "/api/threads" && c.method === "POST");
    expect(post?.body).toEqual({ title: "New chat", bot_id: ember.id });
    expect(openThread).toHaveBeenCalledWith("sage-1");
  });
});
