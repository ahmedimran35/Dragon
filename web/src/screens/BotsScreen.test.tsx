import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setLocaleSetting } from "../i18n";
import type { Bot } from "../types";
import { BotsScreen } from "./BotsScreen";

const toast = vi.fn();
const dispatch = vi.fn();
const setTab = vi.fn();

vi.mock("../store", () => ({
  useStore: () => ({
    state: {
      bots: serverBots,
      profile: null,
      loaded: true,
      connected: true,
      mishapAt: 0,
      finishedAt: 0,
    },
    dispatch,
    toast,
    setTab,
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

const sage: Bot = {
  ...ember,
  id: "b_9f3ab2c1",
  name: "Sage",
  avatar: "",
  emoji: "🌿",
  color: "#059669",
  tagline: "Slow, careful answers",
  instructions: "Answers in short, careful sentences.",
};

/** What the runtime holds: the mocked fetch reads and writes this list. */
let serverBots: Bot[] = [];

const calls: Array<{ url: string; method: string; body: Record<string, unknown> | null }> = [];

const REFUSED = "The default bot or the last bot cannot be deleted.";

beforeEach(() => {
  serverBots = [ember, sage];
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
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? (JSON.parse(String(init.body)) as Record<string, unknown>) : null;
      calls.push({ url: u, method, body });
      const ok = (payload: unknown) => ({ ok: true, status: 200, json: async () => payload });
      const fail = (status: number, payload: unknown) => ({ ok: false, status, json: async () => payload });
      if (u === "/api/bots" && method === "GET") return ok({ bots: serverBots });
      if (u === "/api/bots" && method === "POST") {
        const bot: Bot = { ...ember, ...(body as Partial<Bot>), id: "b_22222222", created_at: 1761009999 };
        serverBots = [...serverBots, bot];
        return ok({ bot });
      }
      const match = /^\/api\/bots\/([^/]+)$/.exec(u);
      if (match && method === "PATCH") {
        const bot: Bot = { ...serverBots.find((b) => b.id === decodeURIComponent(match[1])), ...(body as Partial<Bot>) } as Bot;
        serverBots = serverBots.map((b) => (b.id === bot.id ? bot : b));
        return ok({ bot });
      }
      if (match && method === "DELETE") {
        const id = decodeURIComponent(match[1]);
        if (id === "default" || serverBots.length <= 1) return fail(400, { error: REFUSED });
        serverBots = serverBots.filter((b) => b.id !== id);
        return ok({ ok: true });
      }
      return fail(404, { detail: "not found" });
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

function renderedText(screen: ReactTestRenderer): string {
  return textOf(screen.toJSON());
}

function button(screen: ReactTestRenderer, label: string) {
  return screen.root.findAllByType("button").find((b) => textOf(b).trim() === label);
}

async function open(screen: ReactTestRenderer, name: string) {
  await act(async () => {
    screen.root.findAllByProps({ "aria-label": name })[0].props.onClick();
  });
}

describe("BotsScreen", () => {
  beforeEach(() => setLocaleSetting("en"));

  it("lists the bots the runtime has", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(BotsScreen));
    });
    const text = renderedText(screen);
    expect(text).toContain("Ember");
    expect(text).toContain("Sage");
    expect(text).toContain("New bot");
    expect(dispatch).toHaveBeenCalledWith({ type: "bots", bots: [ember, sage] });
  });

  it("creates a bot from the form", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(BotsScreen));
    });
    await act(async () => {
      button(screen, "New bot")?.props.onClick();
    });
    await act(async () => {
      screen.root.findAllByProps({ "aria-label": "Name" })[0].props.onChange({ target: { value: "Scout" } });
      screen.root.findAllByProps({ placeholder: "What this bot is for, and how it should do it." })[0].props.onChange({
        target: { value: "Books trips." },
      });
    });
    await act(async () => {
      button(screen, "Create")?.props.onClick();
    });
    const post = calls.find((c) => c.url === "/api/bots" && c.method === "POST");
    expect(post).toBeDefined();
    expect(post?.body).toMatchObject({ name: "Scout", instructions: "Books trips." });
    // the save lands and the roster comes back fresh, with the new bot on it
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(renderedText(screen)).toContain("Scout");
  });

  it("edits a bot and patches it", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(BotsScreen));
    });
    await open(screen, "Sage");
    // the editor opens on the bot's own words
    expect(screen.root.findAllByProps({ "aria-label": "Tagline" })[0].props.value).toBe("Slow, careful answers");
    await act(async () => {
      screen.root.findAllByProps({ "aria-label": "Name" })[0].props.onChange({ target: { value: "Sage Prime" } });
    });
    await act(async () => {
      button(screen, "Save")?.props.onClick();
    });
    const patch = calls.find((c) => c.method === "PATCH");
    expect(patch?.url).toBe("/api/bots/b_9f3ab2c1");
    expect(patch?.body).toMatchObject({ name: "Sage Prime", instructions: "Answers in short, careful sentences." });
    expect(toast).toHaveBeenCalledWith("Saved");
  });

  it("shows the runtime's message when a bot cannot be deleted", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(BotsScreen));
    });
    await open(screen, "Ember");
    await act(async () => {
      button(screen, "Delete bot")?.props.onClick();
    });
    await act(async () => {
      button(screen, "Delete")?.props.onClick();
    });
    const del = calls.find((c) => c.method === "DELETE");
    expect(del?.url).toBe("/api/bots/default");
    expect(renderedText(screen)).toContain(REFUSED);
    expect(screen.root.findAllByProps({ role: "alert" }).length).toBeGreaterThan(0);
  });

  it("deletes a bot that can go", async () => {
    let screen!: ReactTestRenderer;
    await act(async () => {
      screen = create(createElement(BotsScreen));
    });
    await open(screen, "Sage");
    await act(async () => {
      button(screen, "Delete bot")?.props.onClick();
    });
    await act(async () => {
      button(screen, "Delete")?.props.onClick();
    });
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/bots/b_9f3ab2c1")).toBe(true);
    const text = renderedText(screen);
    expect(text).toContain("Ember");
    expect(text).not.toContain("Sage");
  });
});
