import { describe, expect, it } from "vitest";
import { emptyWatch, FRAMES_KEPT, trackBrowser, trailOf } from "./browser";
import type { BrowserEvent } from "./types";

function frame(id: string, frameId: string, action: string, thread = "main"): BrowserEvent {
  return {
    type: "browser",
    id,
    ts: "2026-10-27T12:00:00Z",
    thread,
    url: "https://example.com/",
    title: "Example",
    action,
    frame: frameId,
    frames: 1,
    status: "live",
  };
}

describe("trackBrowser", () => {
  it("makes the newest frame the one on screen", () => {
    const w = trackBrowser(emptyWatch, frame("c1", "f1", "Opened example.com"));
    expect(w.latest?.frame).toBe("f1");
    expect(w.seen).toHaveLength(1);
  });

  it("keeps the frames before it as the trail, newest first", () => {
    let w = emptyWatch;
    w = trackBrowser(w, frame("c1", "f1", "Opened example.com"));
    w = trackBrowser(w, frame("c1", "f2", "Clicked 'Search'"));
    w = trackBrowser(w, frame("c1", "f3", "You typed"));
    expect(w.seen.map((e) => e.frame)).toEqual(["f3", "f2", "f1"]);
    expect(trailOf(w).map((e) => e.action)).toEqual(["Clicked 'Search'", "Opened example.com"]);
  });

  it("updates rather than adds when a frame id repeats (a status patch)", () => {
    let w = trackBrowser(emptyWatch, frame("c1", "f1", "Opened example.com"));
    w = trackBrowser(w, { ...frame("c1", "f1", "Opened example.com"), status: "done" });
    expect(w.seen).toHaveLength(1);
    expect(w.latest?.status).toBe("done");
  });

  it("caps the trail", () => {
    let w = emptyWatch;
    for (let i = 0; i < FRAMES_KEPT + 5; i++) w = trackBrowser(w, frame("c1", `f${i}`, `Step ${i}`));
    expect(w.seen).toHaveLength(FRAMES_KEPT);
    expect(w.seen[0].frame).toBe(`f${FRAMES_KEPT + 4}`);
  });

  it("follows the browser across chats", () => {
    let w = trackBrowser(emptyWatch, frame("c1", "f1", "Opened a.example", "main"));
    w = trackBrowser(w, frame("c2", "f2", "Opened b.example", "side"));
    expect(w.latest?.thread).toBe("side");
    expect(w.seen.map((e) => e.thread)).toEqual(["side", "main"]);
  });
});
