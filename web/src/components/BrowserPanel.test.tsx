import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { emptyWatch, trackBrowser, type BrowserWatch } from "../browser";
import { setLocaleSetting } from "../i18n";
import type { BrowserEvent } from "../types";
import { BrowserPanel } from "./BrowserPanel";

/** The slice of the store the panel reads; hoisted so the module mock below can use it. */
const state = vi.hoisted(() => ({
  profile: null as { name?: string } | null,
  holds: [] as unknown[],
  settings: null as { connectors: { browser: boolean } } | null,
  browser: { latest: null, seen: [] } as { latest: BrowserEvent | null; seen: BrowserEvent[] },
}));

vi.mock("../store", () => ({
  useStore: () => ({
    state,
    toast: () => {},
    setBrowserOpen: () => {},
  }),
}));

vi.mock("../api", () => ({
  api: { browserControl: vi.fn(() => Promise.resolve({})) },
  frameUrl: (thread: string, frame: string) => `/frames/${thread}/${frame}.jpg`,
}));

function frame(frameId: string, action: string, title: string): BrowserEvent {
  return {
    type: "browser",
    id: `c-${frameId}`,
    ts: "2026-10-27T12:00:00Z",
    thread: "main",
    url: "https://example.com/",
    title,
    action,
    frame: frameId,
    frames: 1,
    status: "live",
  };
}

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

beforeEach(() => {
  setLocaleSetting("en");
  state.browser = emptyWatch;
  state.settings = null;
});

afterEach(() => screen?.unmount());

describe("BrowserPanel", () => {
  it("says the browser is quiet when nothing has happened, and how to turn it on", async () => {
    state.settings = { connectors: { browser: false } };
    await act(async () => {
      screen = create(createElement(BrowserPanel));
    });
    expect(renderedText()).toContain("The browser is quiet.");
    expect(renderedText()).toContain("Turn it on under Settings");
  });

  it("shows the live frame and what the agent did to get there", async () => {
    state.browser = trackBrowser(emptyWatch, frame("f1", "Opened example.com", "Example"));
    await act(async () => {
      screen = create(createElement(BrowserPanel));
    });
    expect(renderedText()).toContain("Example");
    expect(renderedText()).toContain("Opened example.com");
    const img = screen.root.findAllByType("img")[0];
    expect(String(img.props.src)).toContain("/frames/main/f1.jpg");
  });

  it("lists the trail of frames before the live one", async () => {
    let w: BrowserWatch = trackBrowser(emptyWatch, frame("f1", "Opened example.com", "Example"));
    w = trackBrowser(w, frame("f2", "Clicked 'Search'", "Results"));
    state.browser = w;
    await act(async () => {
      screen = create(createElement(BrowserPanel));
    });
    expect(renderedText()).toContain("What it looked at");
    expect(renderedText()).toContain("Opened example.com");
  });
});
