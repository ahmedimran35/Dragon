import { describe, expect, it } from "vitest";
import { asIdea, catalogue } from "./index";

describe("the Ideas catalogue", () => {
  it("has six sections of four ideas in both languages, with the same ids", () => {
    const en = catalogue("en");
    const zh = catalogue("zh-CN");
    expect(en.sections.map((s) => s.id)).toEqual(["travel", "work", "life", "learn", "family", "more"]);
    expect(zh.sections.map((s) => s.id)).toEqual(en.sections.map((s) => s.id));
    for (const [i, s] of en.sections.entries()) {
      expect(s.ideas).toHaveLength(4);
      expect(zh.sections[i].ideas.map((x) => x.id)).toEqual(s.ideas.map((x) => x.id));
    }
    expect(catalogue("fr")).toBe(en);
  });

  it("turns a catalogue idea into the page's shape", () => {
    const routine = catalogue("en").sections.flatMap((s) => s.ideas).find((x) => x.kind === "ROUTINE")!;
    const idea = asIdea(routine);
    expect(idea.kind).toBe("routine");
    expect(idea.time).toMatch(/^\d{2}:\d{2}$/);
    expect(idea.detail).toBe(routine.body);
    expect(idea.emoji).toBe(routine.emoji);
  });
});
