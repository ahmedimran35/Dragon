import { Shuffle } from "lucide-react";
import { useId, useMemo, useState, type ReactNode } from "react";
import { useT } from "../i18n";
import type { Profile } from "../types";
import { cx } from "../util";
import { Avatar } from "./Avatar";
import { AvatarPicker } from "./AvatarPicker";

/** The part of the profile that is who the agent is: name, tagline, face, voice. */
export type Identity = Pick<Profile, "name" | "tagline" | "avatar" | "emoji" | "color" | "tone" | "communication" | "style" | "user_name">;

export const NAME_MAX = 20;
export const TAGLINE_MAX = 60;

/** Names people give a helper: short, sayable, none of them a brand. Six at a time, shuffled. */
const SUGGESTED_NAMES = ["Dragon", "Veda", "Nova", "Pip", "Sage", "Juno", "Kit", "Wren", "Iris", "Milo", "Echo", "Remy", "Otto", "Luna", "Ari", "Bea", "Nico", "Zed", "小墨", "阿柒", "小满", "知了", "豆豆", "小竹"];

export const TONES = ["formal", "casual", "playful", "concise"] as const;
export const COMMUNICATION = ["short", "detailed", "bullets"] as const;

const TONE_LABELS: Record<(typeof TONES)[number], string> = { formal: "Formal", casual: "Casual", playful: "Playful", concise: "Concise" };
const COMM_LABELS: Record<(typeof COMMUNICATION)[number], string> = { short: "Short replies", detailed: "Detailed", bullets: "Bullet points" };

/** The word a stored tone stands for (a dictionary key), or null when it is unset or not one. */
export function toneLabel(tone: string): string | null {
  return (TONES as readonly string[]).includes(tone) ? TONE_LABELS[tone as (typeof TONES)[number]] : null;
}

/** The word a stored communication setting stands for, or null when it is unset or not one. */
export function commLabel(communication: string): string | null {
  return (COMMUNICATION as readonly string[]).includes(communication) ? COMM_LABELS[communication as (typeof COMMUNICATION)[number]] : null;
}

function pickSix(exclude: string, seed: number): string[] {
  const pool = SUGGESTED_NAMES.filter((n) => n !== exclude);
  // a deterministic shuffle from the seed, so a re-render does not reshuffle
  const out: string[] = [];
  let x = seed || 1;
  const copy = [...pool];
  while (out.length < 6 && copy.length) {
    x = (x * 9301 + 49297) % 233280;
    out.push(copy.splice(x % copy.length, 1)[0]);
  }
  return out;
}

/** The small-caps label over a field or a pick group. */
export function FieldLabel({ htmlFor, children }: { htmlFor?: string; children: ReactNode }) {
  return (
    <label htmlFor={htmlFor} className="block text-[11px] font-semibold uppercase tracking-[0.07em] text-muted">
      {children}
    </label>
  );
}

/** A pill choice: a tone, a length, a suggested name. Clicking the one that is set clears it. */
export function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx(
        "rounded-full border px-3 py-1.5 text-[12.5px] transition-all active:scale-[0.97]",
        active
          ? "border-accent/25 bg-accent-soft font-semibold text-accent-soft-fg shadow-sm"
          : "border-border/50 bg-surface text-muted hover:border-border hover:bg-surface-2 hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

/** One labelled group of pills on its warm tray. */
function Segments({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <FieldLabel>{label}</FieldLabel>
      <div className="mt-1.5 flex flex-wrap gap-1 rounded-2xl border border-border/50 bg-surface-2/60 p-1">{children}</div>
    </div>
  );
}

/**
 * The name and the line under it: what the persona is called and what it says it is. The
 * name ideas are a jump-off point, not a picker — anything sayable can be typed instead.
 */
export function IdentityNameFields({
  value,
  onChange,
  inputCls,
  suggestions = true,
}: {
  value: Identity;
  onChange: (v: Identity) => void;
  inputCls: string;
  /** six shuffled name ideas and a shuffle button (the Bots screen; Settings has a name already) */
  suggestions?: boolean;
}) {
  const t = useT();
  const ids = useId();
  const [seed, setSeed] = useState(7);
  const names = useMemo(() => pickSix(value.name, seed), [value.name, seed]);
  const set = (patch: Partial<Identity>) => onChange({ ...value, ...patch });
  return (
    <div className="space-y-3">
      <div>
        <FieldLabel htmlFor={`${ids}-name`}>{t("Name")}</FieldLabel>
        <input
          id={`${ids}-name`}
          value={value.name}
          onChange={(e) => set({ name: e.target.value.slice(0, NAME_MAX) })}
          maxLength={NAME_MAX}
          className={cx(inputCls, "mt-1.5 text-[15px] font-semibold")}
          placeholder="Dragon"
          aria-label={t("Name")}
          autoCapitalize="words"
        />
      </div>
      <div>
        <FieldLabel htmlFor={`${ids}-tagline`}>{t("Tagline")}</FieldLabel>
        <input
          id={`${ids}-tagline`}
          value={value.tagline}
          onChange={(e) => set({ tagline: e.target.value.slice(0, TAGLINE_MAX) })}
          maxLength={TAGLINE_MAX}
          className={cx(inputCls, "mt-1.5 text-[14px]")}
          placeholder={t("A line under the name, e.g. Your day, sorted.")}
          aria-label={t("Tagline")}
        />
      </div>
      {suggestions && (
        <div className="flex flex-wrap items-center gap-1.5">
          {names.map((n) => (
            <Chip key={n} active={value.name === n} onClick={() => set({ name: n })}>
              {n}
            </Chip>
          ))}
          <button
            type="button"
            onClick={() => setSeed((s) => s + 1)}
            aria-label={t("More names")}
            className="rounded-full border border-border/50 bg-surface p-1.5 text-muted transition hover:border-border hover:bg-surface-2 hover:text-fg"
          >
            <Shuffle size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

/** How the persona talks: the tone, how much it says, and anything else about it. */
export function IdentityVoice({
  value,
  onChange,
  inputCls,
}: {
  value: Identity;
  onChange: (v: Identity) => void;
  inputCls: string;
}) {
  const t = useT();
  const ids = useId();
  const set = (patch: Partial<Identity>) => onChange({ ...value, ...patch });
  return (
    <div className="space-y-4">
      <Segments label={t("Tone")}>
        {TONES.map((tone) => (
          <Chip key={tone} active={value.tone === tone} onClick={() => set({ tone: value.tone === tone ? "" : tone })}>
            {t(TONE_LABELS[tone])}
          </Chip>
        ))}
      </Segments>
      <Segments label={t("How much it says")}>
        {COMMUNICATION.map((c) => (
          <Chip key={c} active={value.communication === c} onClick={() => set({ communication: value.communication === c ? "" : c })}>
            {t(COMM_LABELS[c])}
          </Chip>
        ))}
      </Segments>
      <div>
        <FieldLabel htmlFor={`${ids}-style`}>{t("Anything else about how it should be")}</FieldLabel>
        <textarea
          id={`${ids}-style`}
          value={value.style}
          onChange={(e) => set({ style: e.target.value })}
          rows={2}
          placeholder={t("e.g. A little witty. Uses metric units. Never uses emoji.")}
          className={cx(inputCls, "mt-1.5 resize-none text-[14px]")}
        />
      </div>
    </div>
  );
}

/**
 * Who a persona is: its name, tagline, face and voice. Used to edit the selected bot's
 * persona on the Bots screen, and on the first-run naming page and under Settings for the
 * runtime's own profile; the same fields, the same limits as the server (`NAME_MAX`,
 * `TAGLINE_MAX`, the tone and communication vocabularies). An empty name falls back to
 * "Dragon" on save.
 */
export function IdentityForm({
  value,
  onChange,
  suggestions = true,
  askUserName = true,
  inputCls,
  onStudio,
}: {
  value: Identity;
  onChange: (v: Identity) => void;
  suggestions?: boolean;
  askUserName?: boolean;
  inputCls: string;
  /** the picker offers the avatar studio (Settings only — setup has no model yet) */
  onStudio?: () => void;
}) {
  const t = useT();
  const ids = useId();
  const set = (patch: Partial<Identity>) => onChange({ ...value, ...patch });
  const preview = { ...value, proactivity: "default" as const, proactive: true, goal_interval_minutes: 60, quiet_hours: "" };

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-4">
        <Avatar profile={preview} size={72} />
        <div className="flex-1 min-w-0">
          <IdentityNameFields value={value} onChange={onChange} inputCls={inputCls} suggestions={suggestions} />
        </div>
      </div>

      <AvatarPicker value={{ avatar: value.avatar, emoji: value.emoji, color: value.color }} onChange={(look) => set(look)} onStudio={onStudio} />

      <IdentityVoice value={value} onChange={onChange} inputCls={inputCls} />
      {askUserName && (
        <div>
          <FieldLabel htmlFor={`${ids}-user`}>{t("What it calls you")}</FieldLabel>
          <input id={`${ids}-user`} value={value.user_name} onChange={(e) => set({ user_name: e.target.value })} maxLength={60} placeholder={t("Your name")} className={cx(inputCls, "mt-1.5 text-[14px]")} />
        </div>
      )}
    </div>
  );
}

/** The identity as the store has it, with defaults for a profile from before these fields. */
export function identityOf(p: Partial<Profile> | null | undefined, fallbackAvatar: string, fallbackColor: string): Identity {
  return {
    name: p?.name ?? "Dragon",
    tagline: p?.tagline ?? "",
    avatar: p?.avatar ?? fallbackAvatar,
    emoji: p?.emoji ?? "✨",
    color: p?.color ?? fallbackColor,
    tone: p?.tone ?? "",
    communication: p?.communication ?? "",
    style: p?.style ?? "",
    user_name: p?.user_name ?? "",
  };
}

/** What to send: trimmed, the empty name back to the default. */
export function identityBody(v: Identity): Identity {
  return { ...v, name: v.name.trim() || "Dragon", tagline: v.tagline.trim(), style: v.style.trim(), user_name: v.user_name.trim() };
}
