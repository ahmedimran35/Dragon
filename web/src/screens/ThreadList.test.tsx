import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setLocaleSetting } from "../i18n";
import type { Bot, ThreadMeta } from "../types";
import { ThreadList } from "./ChatScreen";

const toast = vi.fn();
const dispatch = vi.fn();

// ThreadList and the avatar inside it read the store; the test gives both their pieces
vi.mock("../store", () => ({
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
};

const sage: Bot = { ...ember, id: "b_9f3ab2c1", name: "Sage", avatar: "", emoji: "🌿", color: "#059669" };

const created: ThreadMeta = {
  id: "side-1",
  title: "Trip",
  created_at: "2026-10-28T09:00:00Z",
  updated_at: "2026-10-28T09:00:00Z",
  busy: false,
  queued: 0,
  events: 0,
  bot_id: "b_9f3ab2c1",
};

const calls: Array<{ url: string; method: string; body: Record<string, unknown> | null }> = [];

beforeEach(() => {
  calls.length = 0;
  toast.mockClear();
  dispatch.mockClear();
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
      return { ok: true, status: 200, json: async () => created };
    }),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  setLocaleSetting("en");
});

function textOf(node: unknown): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textOf).join(" ");
  if (node && typeof node === "object" && "children" in node) {
    return textOf((node as { children: unknown }).children);
  }
  return "";
}

async function newChat(title: string, onPick = vi.fn()) {
  let screen!: ReactTestRenderer;
  await act(async () => {
    screen = create(createElement(ThreadList, { threads: [], active: "main", onPick }));
  });
  await act(async () => {
    screen.root.findAllByType("input")[0].props.onChange({ target: { value: title } });
  });
  await act(async () => {
    screen.root.findAllByProps({ "aria-label": "New" })[0].props.onClick();
  });
  return onPick;
}

describe("new chats", () => {
  // the labels looked for are the English ones, whatever the machine running the suite speaks
  beforeEach(() => setLocaleSetting("en"));

  it("creates them with no bot: a new chat is always the chief's", async () => {
    const onPick = await newChat("Trip");
    const post = calls.find((c) => c.url === "/api/threads" && c.method === "POST");
    expect(post).toBeDefined();
    expect(post?.body).toEqual({ title: "Trip" });
    expect(onPick).toHaveBeenCalledWith("side-1");
  });

  it("still opens the chat that comes back", async () => {
    const onPick = await newChat("Notes");
    expect(onPick).toHaveBeenCalledWith("side-1");
  });
});

describe("the chats list", () => {
  beforeEach(() => setLocaleSetting("en"));

  it("carries the face and the name of the staff bot whose chat it is", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(
        createElement(ThreadList, {
          threads: [{ ...created, id: "sage-1", title: "Trip planning", bot_id: sage.id }],
          active: "main",
          onPick: vi.fn(),
        }),
      );
    });
    const text = textOf(screen.toJSON());
    expect(text).toContain("Trip planning");
    expect(text).toContain("Sage");
    // the bot's own face, as the row's avatar
    expect(screen.root.findAllByProps({ role: "img" }).length).toBeGreaterThan(0);
  });
});
