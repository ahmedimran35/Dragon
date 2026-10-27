import { cx } from "../util";

/**
 * The app's own mark: three wing ridges on a warm charcoal tile, `public/icon.svg`. It
 * stands for the app where the app speaks for itself — the token door, the first seconds
 * before the socket is up — never for the Dragon: the face is the Dragon, the mark is the
 * app.
 */
export function BrandMark({ size = 72, className }: { size?: number; className?: string }) {
  return <img src="/icon.svg" alt="Dragon" width={size} height={size} draggable={false} className={cx("block shrink-0 select-none", className)} style={{ width: size, height: size }} />;
}
