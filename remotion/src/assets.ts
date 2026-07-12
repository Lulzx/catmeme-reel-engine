import { staticFile } from "remotion";

/**
 * Resolve an asset path. Locally, `assetsBase` is "" and paths are public/-relative
 * (served via staticFile). A future cloud port can pass an absolute https base and
 * the same manifest renders unchanged.
 */
export const asset = (base: string, path: string): string => {
  if (!path) return path;
  if (/^https?:\/\//.test(path)) return path;
  if (base && /^https?:\/\//.test(base)) return base.replace(/\/$/, "") + "/" + path;
  return staticFile(path);
};

/** decibels -> linear gain for <Audio volume>. */
export const dbToLin = (db: number): number => Math.pow(10, db / 20);
