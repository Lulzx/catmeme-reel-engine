import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { TokenT } from "./schema";

const CAPTION_FONT = '"Helvetica Neue", Arial, system-ui, sans-serif';
const WORDS_PER_GROUP = 5;

/**
 * Word-synced subtitles in the wojak / Low Budget Stories style: a few big words
 * at a time, bottom-center, the active word highlighted. `tokens` are
 * scene-relative ({text, startMs, endMs}).
 */
export const Captions: React.FC<{ tokens: TokenT[] }> = ({ tokens }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Drop standalone punctuation tokens (whisper emits lone " , . ) so captions
  // only ever show real words.
  const words = tokens.filter((t) => /[A-Za-z0-9]/.test(t.text));
  if (!words.length) return null;

  const ms = (frame / fps) * 1000;

  // Find the active token (or the nearest one at the edges).
  let activeIdx = words.findIndex((t) => ms >= t.startMs && ms < t.endMs);
  if (activeIdx === -1) {
    if (ms < words[0].startMs) activeIdx = 0;
    else activeIdx = words.length - 1;
  }

  const groupIdx = Math.floor(activeIdx / WORDS_PER_GROUP);
  const group = words.slice(groupIdx * WORDS_PER_GROUP, groupIdx * WORDS_PER_GROUP + WORDS_PER_GROUP);
  const groupStartIdx = groupIdx * WORDS_PER_GROUP;

  // Gentle pop as each group appears.
  const groupStartMs = group[0].startMs;
  const appear = interpolate(ms, [groupStartMs - 80, groupStartMs + 70], [0.35, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 92 }}>
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "0 12px",
          maxWidth: "74%",
          opacity: appear,
          fontFamily: CAPTION_FONT,
          fontWeight: 700,
          fontSize: 46,
          lineHeight: 1.2,
          letterSpacing: 0.2,
        }}
      >
        {group.map((t, i) => {
          const isActive = groupStartIdx + i === activeIdx;
          return (
            <span
              key={i}
              style={{
                color: isActive ? "#ffdf7e" : "#f3f3f3",
                textShadow: "2px 2px 0 rgba(0,0,0,0.9), 0 0 5px rgba(0,0,0,0.55)",
              }}
            >
              {t.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** Pinned italic action/dialogue line near the top — the meme "caption" beat. */
export const ActionCaption: React.FC<{ text: string }> = ({ text }) => {
  return (
    <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 70 }}>
      <div
        style={{
          fontFamily: '"Arial", system-ui, sans-serif',
          fontStyle: "italic",
          fontWeight: 700,
          fontSize: 52,
          color: "#fff",
          textAlign: "center",
          maxWidth: "80%",
          textShadow: "3px 3px 0 #000, -3px 3px 0 #000, 3px -3px 0 #000, -3px -3px 0 #000",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
