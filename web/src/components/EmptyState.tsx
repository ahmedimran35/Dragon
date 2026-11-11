import type { ReactNode } from "react";
import { cx } from "../util";

/**
 * The empty state for the four list screens and the chat intro card. A centered icon,
 * a one-line headline, a paragraph, and up to three chip CTAs. Two flavors:
 *   - the default: bordered card on the canvas, used by Resources / Feed / Goals / etc.
 *   - soft: gradient wash, used by the chat welcome (hero feel).
 *
 * Same shape across the app, so moving from "I've never seen this screen" to "I've seen
 * it once" doesn't change the design vocabulary.
 */
export function EmptyState({
  icon,
  headline,
  body,
  chips,
  tone = "border",
  className,
}: {
  /** An emoji or short glyph centered in a soft ring; never larger than ~32px. */
  icon?: ReactNode;
  /** One sentence, in the app's headline size (~22px). What this screen is for. */
  headline: ReactNode;
  /** One short paragraph: how this screen is useful; no marketing, no exclamation. */
  body?: ReactNode;
  /** Up to three chip buttons, horizontal on wide, stacked on the chat intro. */
  chips?: Array<{ label: ReactNode; onClick: () => void }>;
  tone?: "border" | "soft";
  className?: string;
}) {
  return (
    <div
      className={cx(
        "mx-auto w-full max-w-md px-5 pt-6 pb-8 text-center",
        tone === "border" && "rounded-card",
        className,
      )}
      style={tone === "border" ? { borderRadius: "var(--dg-radius-card)" } : undefined}
    >
      {icon && (
        <div
          className={cx(
            "mx-auto mb-3 flex items-center justify-center",
            tone === "soft"
              ? "h-20 w-20 rounded-full bg-accent-soft text-accent ring-1 ring-border/40 shadow-sm"
              : "h-14 w-14 rounded-full bg-surface-2 text-fg",
          )}
        >
          {icon}
        </div>
      )}
      <h3 className="text-[20px] font-semibold leading-tight tracking-tight">{headline}</h3>
      {body && <p className="mt-2 text-[14px] leading-relaxed text-muted">{body}</p>}
      {chips && chips.length > 0 && (
        <div
          className={cx(
            "mt-4 grid gap-2",
            chips.length <= 2 ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2",
          )}
        >
          {chips.map((c, i) => (
            <button
              key={i}
              type="button"
              onClick={c.onClick}
              className="flex items-center justify-between gap-2 rounded-2xl border border-border/55 bg-surface px-4 py-3 text-left text-[13.5px] transition-all hover:-translate-y-0.5 hover:border-border hover:shadow-md active:scale-[0.98]"
            >
              <span>{c.label}</span>
              <span aria-hidden className="text-muted">
                →
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Border + on-canvas flavor, for list screens. */
export function EmptyCard(props: Omit<Parameters<typeof EmptyState>[0], "tone">) {
  return <EmptyState {...props} tone="border" />;
}
