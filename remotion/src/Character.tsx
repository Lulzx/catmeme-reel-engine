import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { asset } from "./assets";
import type { CharacterT } from "./schema";

const LABEL_FONT = '"Arial Black", Impact, system-ui, sans-serif';

export const Character: React.FC<{ ch: CharacterT; assetsBase: string }> = ({
  ch,
  assetsBase,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Wojak-style entrance: a snappy spring so the character "pops" into the scene.
  const p = spring({ frame, fps, config: { damping: 12, stiffness: 140, mass: 0.6 } });

  const { x, y, width, height } = ch.rect;
  let tx = 0;
  let ty = 0;
  let scale = 1;
  let opacity = 1;
  switch (ch.enter) {
    case "slideLeft":
      tx = interpolate(p, [0, 1], [-width * 0.6, 0]);
      opacity = interpolate(p, [0, 0.4, 1], [0, 1, 1]);
      break;
    case "slideRight":
      tx = interpolate(p, [0, 1], [width * 0.6, 0]);
      opacity = interpolate(p, [0, 0.4, 1], [0, 1, 1]);
      break;
    case "bounce":
      ty = interpolate(p, [0, 1], [-height * 0.5, 0]);
      opacity = interpolate(p, [0, 0.3, 1], [0, 1, 1]);
      break;
    case "pop":
      scale = interpolate(p, [0, 1], [0.6, 1]);
      opacity = interpolate(p, [0, 0.5, 1], [0, 1, 1]);
      break;
    case "none":
    default:
      break;
  }

  // Tiny breath only — the Camera now provides the motion, and the cat must stay
  // locked to the background as the whole world moves together.
  const bobY = ty + Math.sin((frame / fps) * 1.7) * 1.5;

  // Resolve the image: a static sprite, or the active frame of a PNG sequence.
  let src: string;
  if (ch.kind === "animated" && ch.seqCount && ch.seqFps) {
    const idx = Math.min(
      ch.seqCount - 1,
      Math.floor((frame / fps) * ch.seqFps) % ch.seqCount,
    );
    const name = String(idx + 1).padStart(4, "0") + ".png";
    src = asset(assetsBase, `${ch.src}/${name}`);
  } else {
    src = asset(assetsBase, ch.src);
  }

  return (
    <>
      <Img
        src={src}
        style={{
          position: "absolute",
          left: x,
          top: y,
          width,
          height,
          objectFit: "contain",
          transform: `translate(${tx}px, ${bobY}px) scale(${scale})${ch.flip ? " scaleX(-1)" : ""}`,
          transformOrigin: "center bottom",
          opacity,
          filter: `${ch.filter && ch.filter !== "none" ? ch.filter + " " : ""}drop-shadow(0 16px 26px rgba(0,0,0,0.55))`,
        }}
      />
      {ch.label ? (
        <div
          style={{
            position: "absolute",
            left: x,
            top: y + height * 0.06,
            width,
            textAlign: "center",
            transform: `translate(${tx}px, ${bobY}px)`,
            opacity,
            fontFamily: LABEL_FONT,
            fontSize: 54,
            color: "#fff",
            letterSpacing: 1,
            textShadow:
              "0 0 6px #000, 3px 3px 0 #000, -3px 3px 0 #000, 3px -3px 0 #000, -3px -3px 0 #000",
          }}
        >
          {ch.label}
        </div>
      ) : null}
    </>
  );
};
