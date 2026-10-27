import { ArrowDown, ArrowLeft, ArrowUp, Check, CornerDownLeft, Globe, Hand, Loader2, RefreshCw, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, frameUrl } from "../api";
import { trailOf } from "../browser";
import { useT } from "../i18n";
import { useStore } from "../store";
import type { BrowserEvent } from "../types";
import { cx, readStorage, relativeTime, writeStorage } from "../util";
import { HoldStrip, holdLine } from "./Cards";

/** How often the picture is refreshed while the person has the page (ms). */
const LIVE_POLL_MS = 1000;
const WIDTH_KEY = "dragon_browser_width";

/**
 * The watching panel: the agent's browser, live, on the right of a wide window. Every page
 * it opens lands here as a frame — the picture, what it did to get there, and the trail of
 * what it looked at before — with the same controls as the viewer sheet: take the page
 * (a hold, contract C1), click it, type into it, open a URL, hand it back. On a phone the
 * panel is hidden and the viewer sheet is the way in.
 */
export function BrowserPanel() {
  const { state, toast, setBrowserOpen } = useStore();
  const t = useT();
  const watch = state.browser;
  const [picked, setPicked] = useState<BrowserEvent | null>(null);
  const [pending, setPending] = useState<"on" | "off" | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [gone, setGone] = useState(false);
  const [width, setWidth] = useState(() => {
    const n = Number(readStorage(WIDTH_KEY));
    return Number.isFinite(n) && n >= 320 && n <= 640 ? n : 380;
  });

  const shown = picked ?? watch.latest;
  const hold = state.holds.find((h) => h.tool === "browser" && (!shown || h.thread === shown.thread)) ?? state.holds.find((h) => h.tool === "browser");
  const control = pending ? pending === "on" : !!hold;

  useEffect(() => setGone(false), [shown?.frame]);
  // the server's word wins once it arrives
  useEffect(() => setPending(null), [hold?.id, hold?.status]);

  const act = useCallback(
    async (body: Parameters<typeof api.browserControl>[1], thread: string) => {
      setBusy(body.action);
      try {
        await api.browserControl(thread, body);
      } catch (e) {
        toast((e as Error).message);
      } finally {
        setBusy(null);
      }
    },
    [toast],
  );

  // while you have the page, the picture follows what you do: a fresh look every second
  useEffect(() => {
    if (!control || !shown || shown.status !== "live") return;
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      void api.browserControl(shown.thread, { action: "look" }).catch(() => undefined);
    }, LIVE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [control, shown]);

  const onTap = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!control || busy || !shown) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    void act({ action: "click", x: Math.min(Math.max(x, 0), 1), y: Math.min(Math.max(y, 0), 1) }, shown.thread);
  };

  const onWheel = (e: React.WheelEvent<HTMLImageElement>) => {
    if (!control || busy || !shown || Math.abs(e.deltaY) < 8) return;
    void act({ action: "scroll", dy: Math.max(-2000, Math.min(2000, Math.round(e.deltaY * 2))) }, shown.thread);
  };

  // the drag on the panel's left edge, remembered for next time
  const startResize = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = width;
    let current = startW;
    const move = (ev: PointerEvent) => {
      current = Math.min(640, Math.max(320, startW + (startX - ev.clientX)));
      setWidth(current);
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      writeStorage(WIDTH_KEY, String(current));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const name = state.profile?.name ?? "Dragon";
  let host = "";
  if (shown) {
    host = shown.url;
    try {
      host = new URL(shown.url).host;
    } catch {
      /* keep the raw url */
    }
  }
  const live = shown?.status === "live";
  const trail = trailOf(watch);
  const browserOn = state.settings?.connectors.browser ?? true;

  return (
    <aside style={{ width }} className="relative hidden h-full shrink-0 flex-col border-l border-border bg-surface/70 wide:flex">
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={t("Resize the panel")}
        onPointerDown={startResize}
        className="absolute left-0 top-0 z-10 h-full w-1.5 cursor-col-resize hover:bg-accent/40"
      />
      <header className="flex items-center gap-2 border-b border-border/70 px-3.5 py-2.5">
        <Globe size={17} className="shrink-0 text-accent" />
        <span className="min-w-0 flex-1 truncate text-[14px] font-semibold">{shown ? shown.title || host : t("Browser")}</span>
        {live && (
          <span className="flex shrink-0 items-center gap-1 rounded-full bg-rose-500/12 px-2 py-0.5 text-[10.5px] font-semibold text-rose-600 dark:text-rose-300">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-rose-500" /> {t("LIVE")}
          </span>
        )}
        <button type="button" onClick={() => setBrowserOpen(false)} aria-label={t("Close")} className="rounded-full p-1.5 text-muted hover:bg-surface-2">
          <X size={16} />
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-3.5 py-3">
        {!shown ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
            <Globe size={26} className="text-muted" />
            <p className="text-[14px] font-semibold">{t("The browser is quiet.")}</p>
            <p className="text-[12.5px] leading-[19px] text-muted">
              {t("When {name} uses the browser, every page it opens shows up here.", { name })}
            </p>
            {!browserOn && <p className="text-[12px] leading-[18px] text-muted">{t("Turn it on under Settings → Model → Connections → Browser.")}</p>}
          </div>
        ) : (
          <>
            {hold && hold.by === "agent" && (
              <div className="mb-2">
                <HoldStrip hold={hold} compact />
              </div>
            )}
            <div className={cx("relative overflow-hidden rounded-2xl border border-border bg-surface-2", control && "ring-2 ring-accent")}>
              {gone ? (
                <div className="flex aspect-[16/10] flex-col items-center justify-center gap-1 text-muted">
                  <Globe size={22} />
                  <span className="text-[12px]">{t("This frame is no longer available.")}</span>
                  <button type="button" onClick={() => void act({ action: "look" }, shown.thread)} className="text-[13px] font-medium text-accent">
                    {t("Look again")}
                  </button>
                </div>
              ) : (
                <img
                  key={shown.frame}
                  src={frameUrl(shown.thread, shown.frame)}
                  alt={shown.title || host}
                  onError={() => setGone(true)}
                  onClick={onTap}
                  onWheel={onWheel}
                  draggable={false}
                  className={cx("block w-full select-none", control && "cursor-crosshair")}
                />
              )}
              {busy && busy !== "look" && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/20">
                  <Loader2 size={24} className="animate-spin text-white" />
                </div>
              )}
            </div>
            <div className="mt-2 flex items-baseline justify-between gap-2 text-[12px] text-muted">
              <span className="truncate">
                {shown.by_user && shown.action.startsWith("You") ? t("You") + shown.action.slice(3) : shown.action}
              </span>
              <span className="shrink-0">{relativeTime(shown.updated_ts || shown.ts)}</span>
            </div>

            {control ? (
              <div className="mt-3 space-y-2">
                <form
                  className="flex items-center gap-1.5"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!text) return;
                    void act({ action: "type", text }, shown.thread).then(() => setText(""));
                  }}
                >
                  <input
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder={t("Type into the focused field…")}
                    aria-label={t("Type into the focused field…")}
                    className="min-w-0 flex-1 rounded-2xl bg-surface-2 px-3 py-2 text-[13px] outline-none"
                    autoComplete="off"
                    autoCapitalize="off"
                  />
                  <button type="submit" disabled={!text || !!busy} aria-label={t("Type")} className="rounded-full bg-accent p-2 text-white disabled:opacity-40">
                    {busy === "type" ? <Loader2 size={15} className="animate-spin" /> : <CornerDownLeft size={15} />}
                  </button>
                </form>
                <form
                  className="flex items-center gap-1.5"
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!url) return;
                    void act({ action: "navigate", url }, shown.thread).then(() => setUrl(""));
                  }}
                >
                  <button type="button" onClick={() => void act({ action: "back" }, shown.thread)} disabled={!!busy} aria-label={t("Back")} className="rounded-full bg-surface-2 p-2 text-fg disabled:opacity-40">
                    <ArrowLeft size={14} />
                  </button>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder={t("Open a URL…")}
                    aria-label={t("Open a URL…")}
                    inputMode="url"
                    autoCapitalize="off"
                    className="min-w-0 flex-1 rounded-2xl bg-surface-2 px-3 py-2 text-[12.5px] outline-none"
                  />
                  <button type="submit" disabled={!url || !!busy} className="rounded-2xl bg-surface-2 px-2.5 py-2 text-[12.5px] font-medium disabled:opacity-40">
                    {t("Go")}
                  </button>
                  <button type="button" onClick={() => void act({ action: "scroll", dy: -600 }, shown.thread)} disabled={!!busy} aria-label={t("Scroll up")} className="rounded-full bg-surface-2 p-2 text-fg disabled:opacity-40">
                    <ArrowUp size={14} />
                  </button>
                  <button type="button" onClick={() => void act({ action: "scroll", dy: 600 }, shown.thread)} disabled={!!busy} aria-label={t("Scroll down")} className="rounded-full bg-surface-2 p-2 text-fg disabled:opacity-40">
                    <ArrowDown size={14} />
                  </button>
                </form>
                <div className="flex items-center justify-between gap-2">
                  <span className="min-w-0 truncate text-[11.5px] text-muted">
                    {hold && hold.by === "agent" ? holdLine(hold, t) : t("You have the page. Press Done when you are finished.")}
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setPending("off");
                      void act({ action: "handed_back" }, shown.thread);
                    }}
                    disabled={busy === "handed_back"}
                    className="flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full bg-fg px-3 py-1.5 text-[12.5px] font-semibold text-bg disabled:opacity-60"
                  >
                    {busy === "handed_back" ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} {t("Done")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-3 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setPending("on");
                    void act({ action: "take_over" }, shown.thread);
                  }}
                  disabled={pending === "on"}
                  className="flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-2 text-[13px] font-semibold text-white disabled:opacity-60"
                >
                  <Hand size={14} /> {t("Take over")}
                </button>
                <button
                  type="button"
                  onClick={() => void act({ action: "look" }, shown.thread)}
                  disabled={!!busy}
                  aria-label={t("Refresh")}
                  className="rounded-full bg-surface-2 p-2 text-muted disabled:opacity-40"
                >
                  {busy === "look" ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
                </button>
                {picked && (
                  <button type="button" onClick={() => setPicked(null)} className="text-[12.5px] font-medium text-accent">
                    {t("Back to live")}
                  </button>
                )}
              </div>
            )}

            {trail.length > 0 && (
              <div className="mt-5">
                <h4 className="text-[12px] font-semibold text-muted">{t("What it looked at")}</h4>
                <ul className="mt-1.5 space-y-1">
                  {trail.map((e) => (
                    <li key={e.frame}>
                      <button
                        type="button"
                        onClick={() => setPicked(e)}
                        className={cx(
                          "flex w-full items-center gap-2.5 rounded-xl px-1.5 py-1.5 text-left hover:bg-surface-2/70",
                          picked?.frame === e.frame && "bg-surface-2",
                        )}
                      >
                        <img src={frameUrl(e.thread, e.frame)} alt="" loading="lazy" className="h-9 w-14 shrink-0 rounded-md border border-border/60 object-cover object-top" />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[12.5px] font-medium">{e.title || e.url}</span>
                          <span className="block truncate text-[11.5px] text-muted">
                            {e.by_user && e.action.startsWith("You") ? t("You") + e.action.slice(3) : e.action} · {relativeTime(e.updated_ts || e.ts)}
                          </span>
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
