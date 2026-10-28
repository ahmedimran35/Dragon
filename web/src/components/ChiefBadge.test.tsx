import { createElement } from "react";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { afterEach, describe, expect, it, vi } from "vitest";
import { isChief } from "../bots";
import { setLocaleSetting } from "../i18n";
import type { Bot } from "../types";
import { BotRoster } from "./BotRoster";

// Avatar follows the mood it is given; its fallback mood hook reads the store
vi.mock("../store", () => ({
  useStore: () => ({ state: { loaded: true, connected: true, mishapAt: 0, finishedAt: 0 } }),
}));

const base: Bot = {
  id: "b_1",
  name: "One",
  avatar: "",
  emoji: "🌙",
  color: "#7c3aed",
  tagline: "",
  tone: "",
  communication: "",
  style: "",
  instructions: "",
  model: "",
  created_at: 1761000000,
};

const named = (id: string, name: string, role?: "chief" | "staff"): Bot => ({ ...base, id, name, role });

function textOf(node: unknown): string {
  if (typeof node === "string") return node;
  if (Array.isArray(node)) return node.map(textOf).join(" ");
  if (node && typeof node === "object" && "children" in node) {
    return textOf((node as { children: unknown }).children);
  }
  return "";
}

let screen: ReactTestRenderer;

afterEach(() => {
  if (screen) act(() => screen.unmount());
  setLocaleSetting("en");
  vi.restoreAllMocks();
});

describe("isChief", () => {
  it("reads the role the runtime sent", () => {
    expect(isChief(named("b_1", "One", "chief"))).toBe(true);
    expect(isChief(named("b_2", "Two", "staff"))).toBe(false);
  });

  it("falls back to the id 'default' when a runtime sends no role", () => {
    expect(isChief(named("default", "Ember"))).toBe(true);
    expect(isChief(named("b_3", "Three"))).toBe(false);
    expect(isChief(null)).toBe(false);
  });
});

describe("the chief-of-staff mark", () => {
  it("shows on the chief's card only, whether the role or the old id marks it", async () => {
    setLocaleSetting("en");
    const bots = [named("default", "Ember"), named("b_2", "Two", "chief"), named("b_3", "Three", "staff"), named("b_4", "Four")];
    await act(async () => {
      screen = create(
        createElement(BotRoster, {
          bots,
          presence: { threads: [], status: { state: "idle", detail: "", thread: "main" }, pendingApprovals: [] },
          onPick: () => undefined,
        }),
      );
    });
    const rows = screen.root.findAllByType("li").map((li) => textOf(li));
    const marked = rows.filter((row) => row.includes("Chief of staff"));
    expect(marked).toHaveLength(2);
    expect(marked.some((row) => row.includes("Ember"))).toBe(true);
    expect(marked.some((row) => row.includes("Two"))).toBe(true);
    // the staff bots carry no mark
    expect(rows.find((row) => row.includes("Three"))?.includes("Chief of staff")).toBe(false);
    expect(rows.find((row) => row.includes("Four"))?.includes("Chief of staff")).toBe(false);
  });
});
