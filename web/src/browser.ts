import type { BrowserEvent } from "./types";

/** How many frames the trail keeps (the runtime keeps as many in memory). */
export const FRAMES_KEPT = 40;

/** The agent's browser as the watching panel shows it, across every chat. */
export interface BrowserWatch {
  /** The newest frame of whatever it is doing in the browser right now. */
  latest: BrowserEvent | null;
  /** The frames seen so far, newest first: the trail of what it looked at. */
  seen: BrowserEvent[];
}

export const emptyWatch: BrowserWatch = { latest: null, seen: [] };

/**
 * A browser card arriving (a new one) or moving on (a new frame): the frame becomes the
 * one on screen, the frames before it stay as the trail. A status patch reuses the frame
 * id, so it updates the entry rather than adding one.
 */
export function trackBrowser(watch: BrowserWatch, ev: BrowserEvent): BrowserWatch {
  const seen = [ev, ...watch.seen.filter((e) => e.frame !== ev.frame)].slice(0, FRAMES_KEPT);
  return { latest: ev, seen };
}

/** The trail under the frame on screen: everything but the newest. */
export function trailOf(watch: BrowserWatch): BrowserEvent[] {
  return watch.seen.slice(1);
}
