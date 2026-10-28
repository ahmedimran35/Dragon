import { Crown } from "lucide-react";
import { useT } from "../i18n";
import { cx } from "../util";

/**
 * The chief-of-staff mark: a small crown and the words on the accent treatment. It sits on
 * the chief's card in the roster, in the chat header when the chat is with the chief, and
 * on the chief's card and hero on the Bots page — so it is always clear which bot runs the
 * roster and which bots are its staff. `compact` is the roster card's tighter row.
 */
export function ChiefBadge({ compact = false, className }: { compact?: boolean; className?: string }) {
  const t = useT();
  return (
    <span
      title={t("It manages the other bots and briefs them.")}
      className={cx(
        "inline-flex shrink-0 items-center gap-1 rounded-full bg-accent-soft font-semibold text-accent-soft-fg ring-1 ring-accent/15",
        compact ? "px-1.5 py-px text-[9px] leading-[13px]" : "px-2 py-0.5 text-[10px] leading-[14px]",
        className,
      )}
    >
      <Crown size={compact ? 10 : 11} strokeWidth={2.25} aria-hidden />
      {t("Chief of staff")}
    </span>
  );
}
