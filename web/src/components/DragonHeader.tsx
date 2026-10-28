import type { ReactNode } from "react";
import type { Bot, Profile, Status } from "../types";
import { cx } from "../util";
import { Avatar } from "./Avatar";

/**
 * Dragon's page header, on the chat and the four tabs: the face
 * centred on its pale disc, the name in a small white tag hanging off the chin with what the
 * agent is doing as the tag's second line, and a round button in each top corner. Two lines
 * are always reserved under the face so the page does not jump when a status appears.
 */
export function DragonHeader({
  profile,
  status,
  name,
  statusLine,
  statusTone = "muted",
  spinning = false,
  badge,
  onAvatar,
  onName,
  leading,
  trailing,
  under,
  size = 72,
  className,
  scrim = false,
}: {
  /** the face on the disc: the bot this chat is with, or the runtime's profile */
  profile: Profile | Bot | null;
  status?: Status;
  name: string;
  statusLine?: string | null;
  /** the second line's colour: muted at rest, accent while working or waiting */
  statusTone?: "muted" | "accent";
  /** a small spinner before the status line */
  spinning?: boolean;
  /** a count on the face's shoulder (queued messages, pending approvals) */
  badge?: number;
  onAvatar?: () => void;
  onName?: () => void;
  leading?: ReactNode;
  trailing?: ReactNode;
  /** a chip beside the name (the chief mark, a side chat's title) */
  under?: ReactNode;
  size?: number;
  className?: string;
  /** a shade over a list that scrolls under the header (the chat), instead of the canvas colour */
  scrim?: boolean;
}) {
  return (
    <header
      className={cx(
        "safe-top relative shrink-0 border-b border-border/60 bg-surface/95 backdrop-blur-md shadow-sm",
        scrim ? "header-scrim" : "",
        className,
      )}
    >
      <div className="flex items-center gap-3 px-5 py-3">
        {leading && <div className="shrink-0">{leading}</div>}
        <button type="button" onClick={onAvatar} aria-label={name} className="relative shrink-0 rounded-full bg-accent-soft ring-1 ring-border/40">
          <Avatar profile={profile} status={status} size={size} />
          {badge !== undefined && badge > 0 && (
            <span className="pointer-events-none absolute -right-0.5 top-0 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-bg bg-rose-500 px-1 text-[10.5px] font-bold text-white">
              {badge}
            </span>
          )}
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <button type="button" onClick={onName ?? onAvatar} className="min-w-0 text-left">
              <span className="block truncate text-[18px] font-semibold tracking-tight text-fg">{name}</span>
            </button>
            {under && <div className="flex shrink-0 items-center gap-1.5">{under}</div>}
          </div>
          {statusLine && (
            <div className={cx("mt-0.5 flex items-center gap-1 text-[12.5px] leading-tight", statusTone === "accent" ? "text-accent" : "text-muted")}>
              {spinning && <span className="h-2.5 w-2.5 shrink-0 animate-spin rounded-full border-[1.5px] border-current border-t-transparent" />}
              <span className="truncate">{statusLine}</span>
            </div>
          )}
        </div>
        {trailing && <div className="shrink-0">{trailing}</div>}
      </div>
    </header>
  );
}

/** Dragon's name tag: a small white tag with a faint shadow, the name in regular weight, the status as a smaller grey line inside the same tag. */
export function DragonNamePill({
  name,
  statusLine,
  statusTone = "muted",
  spinning = false,
  onClick,
}: {
  name: string;
  statusLine?: string | null;
  statusTone?: "muted" | "accent";
  spinning?: boolean;
  onClick?: () => void;
}) {
  const inner = (
    <>
      <span className="max-w-[240px] truncate text-[14px] leading-[18px] text-fg">{name}</span>
      {statusLine && (
        <span className={cx("mt-0.5 flex max-w-[240px] items-center gap-1 text-[11.5px] leading-[14px]", statusTone === "accent" ? "text-accent" : "text-muted")}>
          {spinning && <span className="h-2.5 w-2.5 shrink-0 animate-spin rounded-full border-[1.5px] border-current border-t-transparent" />}
          <span className="truncate">{statusLine}</span>
        </span>
      )}
    </>
  );
  const cls = "flex flex-col items-center rounded-[14px] bg-surface px-3 py-1 shadow-[0_1px_4px_rgba(0,0,0,0.16)] dark:border dark:border-border dark:shadow-none";
  return onClick ? (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  ) : (
    <div className={cls}>{inner}</div>
  );
}

/** Dragon's corner button: a white disc with one glyph, lifted by a soft shadow (a hairline in the dark). */
export function DragonRoundButton({
  onClick,
  label,
  children,
  dot = false,
  small = false,
  className,
  disabled = false,
  expanded,
}: {
  onClick: () => void;
  label: string;
  children: ReactNode;
  /** a small accent dot at the top right (something is waiting behind it) */
  dot?: boolean;
  /** the 40px disc of a page bar rather than the 44px one of the home header */
  small?: boolean;
  className?: string;
  disabled?: boolean;
  /** for a button that opens a menu */
  expanded?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-haspopup={expanded === undefined ? undefined : "menu"}
      aria-expanded={expanded}
      disabled={disabled}
      className={cx(
        "relative flex items-center justify-center rounded-full bg-surface text-fg shadow-[0_1px_4px_rgba(0,0,0,0.14)] hover:bg-surface-2 disabled:opacity-50 dark:border dark:border-border dark:shadow-none",
        small ? "h-10 w-10" : "h-11 w-11",
        className,
      )}
    >
      {children}
      {dot && <span className="absolute right-[3px] top-[3px] h-[9px] w-[9px] rounded-full border-[1.5px] border-surface bg-accent" />}
    </button>
  );
}

/** Dragon's big left-aligned page title ("Goals", "Tasks"). */
export function DragonPageTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <h1 className={cx("px-5 pt-1.5 pb-1.5 text-[26px] font-bold leading-8 tracking-tight", className)}>{children}</h1>;
}
