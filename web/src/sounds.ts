/**
 * Two sounds, opt-in (Settings → Notifications → "Play a sound"), synthesised with the
 * Web Audio's oscillator — no asset ships. Each is one short gesture well under a second,
 * quiet by gain, and honour the system's reduced-sound tendencies by simply being short
 * and soft; the AudioContext is created lazily on the first play (a page may start one
 * before any gesture and find it suspended, so a play resumes it too).
 *
 *  - `agentDone` — a soft two-note settle, when a turn ends and no approval is waiting.
 *  - `approvalsWaiting` — a gentle pickup, when the approvals queue goes from empty to not.
 */

const SOUND_KEY = "dragon_sounds";

/** Whether sounds are on; off by default, remembered in localStorage. */
export function soundsEnabled(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) === "1";
  } catch {
    return false;
  }
}

export function setSoundsEnabled(on: boolean): void {
  try {
    if (on) localStorage.setItem(SOUND_KEY, "1");
    else localStorage.removeItem(SOUND_KEY);
  } catch {
    /* storage off: the choice lasts for this page */
  }
}

let ctx: AudioContext | null = null;

function context(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
  return ctx;
}

/** One sine note: pitch in Hz, when it starts (s), how long it lasts (s), how loud (0–1). */
function note(ac: AudioContext, freq: number, at: number, dur: number, gain: number): void {
  const osc = ac.createOscillator();
  const env = ac.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  // a fast rise and a slow fall reads as a chime, not a beep
  env.gain.setValueAtTime(0.0001, at);
  env.gain.exponentialRampToValueAtTime(gain, at + 0.02);
  env.gain.exponentialRampToValueAtTime(0.0001, at + dur);
  osc.connect(env).connect(ac.destination);
  osc.start(at);
  osc.stop(at + dur + 0.02);
}

/** A turn ended and nothing is waiting: the fifth G4→D5, soft, ~350ms. */
export function agentDone(): void {
  if (!soundsEnabled()) return;
  const ac = context();
  if (!ac) return;
  const t0 = ac.currentTime + 0.01;
  note(ac, 392, t0, 0.22, 0.08);
  note(ac, 587.33, t0 + 0.14, 0.3, 0.07);
}

/** The approvals queue went 0 → N: a pickup D5→A5, a shade brighter, ~300ms. */
export function approvalsWaiting(): void {
  if (!soundsEnabled()) return;
  const ac = context();
  if (!ac) return;
  const t0 = ac.currentTime + 0.01;
  note(ac, 587.33, t0, 0.18, 0.09);
  note(ac, 880, t0 + 0.12, 0.26, 0.08);
}
