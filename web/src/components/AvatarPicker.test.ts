import { describe, expect, it } from "vitest";
import type { Bot } from "../types";
import { AVATAR_COLORS, AVATAR_EMOJI, suggestedFaces } from "./AvatarPicker";

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

const wearing = (id: string, look: Partial<Bot>): Bot => ({ ...base, ...look, id });

/** The default bot wears the dragon; Sage wears the green leaf. */
const ember = wearing("default", { avatar: "dragon", emoji: "", color: "" });
const sage = wearing("b_2", { avatar: "", emoji: "🌿", color: "#059669" });

describe("suggestedFaces", () => {
  it("skips the faces the existing bots wear: the dragon, the leaf, the green", () => {
    const suggestions = suggestedFaces([ember, sage], 20);
    expect(suggestions.every((f) => f.avatar !== "dragon")).toBe(true);
    expect(suggestions.every((f) => f.emoji !== "🌿")).toBe(true);
    expect(suggestions.every((f) => f.color !== "#059669")).toBe(true);
    // the first suggestion is the first fresh face of the vocabulary: the sparkle on blue
    expect(suggestions[0]).toEqual({ avatar: "", emoji: AVATAR_EMOJI[0], color: AVATAR_COLORS[0] });
  });

  it("offers the dragon first when no bot wears it", () => {
    expect(suggestedFaces([sage], 5)[0]).toEqual({ avatar: "dragon", emoji: "", color: "" });
    expect(suggestedFaces([], 5)[0]).toEqual({ avatar: "dragon", emoji: "", color: "" });
  });

  it("never suggests the same face twice over two new bots", () => {
    const first = suggestedFaces([ember, sage], 1)[0];
    const second = suggestedFaces([ember, sage, wearing("b_3", first)], 1)[0];
    expect(second).toBeDefined();
    expect(second).not.toEqual(first);
    expect(second.emoji !== first.emoji && second.color !== first.color).toBe(true);
  });

  it("orders neighbours apart: every emoji, colours stepping beside it", () => {
    const row = suggestedFaces([], 17);
    // the dragon leads, then the sixteen emoji each once, with no two colours side by side alike
    expect(row[0].avatar).toBe("dragon");
    const emoji = row.slice(1).map((f) => f.emoji);
    expect(new Set(emoji).size).toBe(AVATAR_EMOJI.length);
  });

  it("keeps the row to the count asked for", () => {
    expect(suggestedFaces([], 4)).toHaveLength(4);
    expect(suggestedFaces([ember, sage], 10)).toHaveLength(10);
  });
});
