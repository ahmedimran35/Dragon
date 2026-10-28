import { Check, Sparkles } from "lucide-react";
import { DRAGON, dragonUrl, isDragon, studioUrl } from "../avatars";
import { useT } from "../i18n";
import type { Bot } from "../types";
import { cx } from "../util";

export const AVATAR_EMOJI = ["✨", "🌙", "🪐", "🌿", "🔥", "🌊", "🦉", "🦊", "🐙", "🎯", "🧭", "💎", "🍀", "🎈", "🤖", "🧠"];
export const AVATAR_COLORS = ["#0064d4", "#7c3aed", "#0891b2", "#059669", "#d97706", "#dc2626", "#db2777", "#4b5563"];

export interface AvatarChoice {
  avatar: string;
  emoji: string;
  color: string;
}

/** The looks a face can be drawn in — the shared list, same ids; the runtime knows the words. */
export const AVATAR_STYLES: { id: string; label: string }[] = [
  { id: "dragon", label: "3D toy (Dragon)" },
  { id: "flat", label: "Flat" },
  { id: "clay", label: "3D clay" },
  { id: "watercolor", label: "Watercolour" },
  { id: "pixel", label: "Pixel" },
  { id: "line", label: "Line" },
  { id: "sticker", label: "Sticker" },
];

/**
 * The dragon, a face drawn for you in the avatar studio (when the profile wears one), a tile
 * that opens the studio (when `onStudio` is given — Settings; setup has no model yet), plus
 * an emoji on a colour for anyone who would rather.
 */
export function AvatarPicker({
  value,
  onChange,
  onStudio,
}: {
  value: AvatarChoice;
  onChange: (v: AvatarChoice) => void;
  /** the "draw a new one" tile: opens the avatar studio screen */
  onStudio?: () => void;
}) {
  const t = useT();
  const emojiMode = value.avatar === "";
  // a face from the studio: anything that is neither the dragon nor the emoji
  const studio = !emojiMode && !isDragon(value.avatar) ? value.avatar : null;
  const ring = "ring-[2.5px] ring-accent ring-offset-2 ring-offset-bg";
  const tile = "relative h-[72px] w-[72px] shrink-0 overflow-hidden rounded-full transition";
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          aria-label={t("The dragon")}
          aria-pressed={value.avatar === DRAGON}
          onClick={() => onChange({ ...value, avatar: DRAGON })}
          className={cx(tile, "bg-[#f1efeb]", value.avatar === DRAGON ? ring : "opacity-90 hover:opacity-100")}
        >
          <img src={dragonUrl(value.avatar === DRAGON ? "happy" : "idle")} alt="" draggable={false} className="h-full w-full object-cover" />
        </button>
        {studio && (
          <button type="button" aria-label={t("The face drawn for you")} aria-pressed className={cx(tile, "bg-surface-2", ring)}>
            <img src={studioUrl(studio, "happy")} alt="" draggable={false} className="h-full w-full object-cover" />
          </button>
        )}
        {onStudio && (
          <button
            type="button"
            aria-label={t("Avatar studio")}
            onClick={onStudio}
            className={cx(tile, "flex items-center justify-center border border-dashed border-border text-accent hover:bg-surface-2")}
          >
            <Sparkles size={22} />
          </button>
        )}
        <button
          type="button"
          aria-label={t("An emoji instead")}
          aria-pressed={emojiMode}
          onClick={() => onChange({ ...value, avatar: "" })}
          className={cx("flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-full text-[26px] transition", emojiMode ? ring : "opacity-90 hover:opacity-100")}
          style={{ background: `linear-gradient(135deg, ${value.color}, color-mix(in srgb, ${value.color} 60%, #ffffff))` }}
        >
          {value.emoji}
        </button>
      </div>
      {emojiMode && (
        <>
          <div className="grid grid-cols-8 gap-1.5">
            {AVATAR_EMOJI.map((e) => (
              <button
                key={e}
                type="button"
                onClick={() => onChange({ ...value, emoji: e })}
                className={cx("flex aspect-square items-center justify-center rounded-2xl bg-surface-2 text-[22px]", value.emoji === e && "ring-2 ring-accent")}
              >
                {e}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            {AVATAR_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                aria-label={c}
                onClick={() => onChange({ ...value, color: c })}
                className="flex h-8 w-8 items-center justify-center rounded-full text-white"
                style={{ background: c }}
              >
                {value.color === c && <Check size={16} />}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/** How many faces the "Suggested" row offers at once. */
export const SUGGESTION_COUNT = 10;

/**
 * The faces a new bot can be suggested: the dragon and every emoji-on-a-colour pair of the
 * picker's vocabulary. The pairs walk the emoji list while the colour steps along beside
 * it, so neighbouring suggestions never look alike, and every emoji meets every colour
 * somewhere in the list.
 */
function faceVocabulary(): AvatarChoice[] {
  const out: AvatarChoice[] = [{ avatar: DRAGON, emoji: "", color: "" }];
  for (let i = 0; i < AVATAR_EMOJI.length * AVATAR_COLORS.length; i++) {
    const e = i % AVATAR_EMOJI.length;
    out.push({ avatar: "", emoji: AVATAR_EMOJI[e], color: AVATAR_COLORS[(Math.floor(i / AVATAR_EMOJI.length) + e) % AVATAR_COLORS.length] });
  }
  return out;
}

/**
 * Faces for a new bot to be suggested, ones the existing bots do not wear first: a face is
 * skipped while some bot wears that dragon, that emoji or that colour, so two bots never
 * start on the same face. When every face is worn the full vocabulary comes back, dragon
 * first.
 */
export function suggestedFaces(existing: Array<Pick<Bot, "avatar" | "emoji" | "color">>, limit = SUGGESTION_COUNT): AvatarChoice[] {
  const dragonWorn = existing.some((b) => !!b.avatar && isDragon(b.avatar));
  const wornFaces = existing.filter((b) => b.avatar === "");
  const emojiWorn = new Set(wornFaces.map((b) => b.emoji || "✨"));
  const colorWorn = new Set(wornFaces.map((b) => b.color || AVATAR_COLORS[0]));
  const worn = (f: AvatarChoice) => (f.avatar === DRAGON ? dragonWorn : emojiWorn.has(f.emoji) || colorWorn.has(f.color));
  const vocabulary = faceVocabulary();
  const fresh = vocabulary.filter((f) => !worn(f));
  return (fresh.length > 0 ? fresh : vocabulary).slice(0, limit);
}
