import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { useMemo } from "react";

/**
 * The missing ingredient vs. Low Budget Stories: a moving CAMERA. We treat the
 * whole scene (background + cat) as one "world" and hard-cut between framings —
 * wide establish, medium, face close-up, punch-in — within a single scene. The
 * rhythm of those cuts (not background changes) is what makes wojak videos feel
 * alive. Zooming the world as one layer also keeps the cat and background locked
 * together, so the cutout reads as part of the shot instead of floating on top.
 *
 * Deterministic: shots are a pure function of (sceneDuration, focus rect, seed).
 * No Math.random — frame-stable for Remotion.
 */
type Rect = { x: number; y: number; width: number; height: number };
type Key = { scale: number; fx: number; fy: number };
type Shot = { start: number; dur: number; from: Key; to: Key; shake: number };

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

function buildShots(total: number, W: number, H: number, rect: Rect | undefined, seed: number): Shot[] {
  // Focal anchors derived from the cat's box (bottom-anchored bust). Frame
  // close-ups on the UPPER BODY (0.33h), not a guessed face at the very top of
  // the box — for odd poses (a screaming cat rearing up) the top of the box is
  // empty air, and clamping to the world edge then shoves the cat off-frame.
  // 0.33h sits reliably on the head/chest mass for every clip.
  const cx = rect ? rect.x + rect.width / 2 : W / 2;
  const faceY = rect ? rect.y + rect.height * 0.33 : H * 0.36;
  const bodyY = rect ? rect.y + rect.height * 0.52 : H * 0.5;
  const est: Key = { scale: 1.07, fx: W / 2, fy: H * 0.46 };
  const med: Key = { scale: 1.4, fx: cx, fy: bodyY };
  const clo: Key = { scale: 1.92, fx: cx, fy: faceY };

  // A move = {from, to, frames, shake}. Mix pushes, drifts, snaps, pull-outs.
  // Backgrounds are now 3840px, so even a 2x punch stays crisp.
  const MOVES = [
    { from: { ...est, scale: 1.05 }, to: { ...est, scale: 1.17 }, f: 46, shake: 0 }, // 0 establish push-in
    { from: med, to: { ...med, scale: 1.48 }, f: 36, shake: 5 }, //                     1 medium drift
    { from: { ...clo, scale: 1.66 }, to: clo, f: 32, shake: 9 }, //                     2 close push
    { from: { ...clo, scale: 2.05 }, to: { ...clo, scale: 1.9 }, f: 22, shake: 14 }, //  3 punch (snap-in)
    { from: { ...med, scale: 1.62 }, to: est, f: 40, shake: 4 }, //                     4 pull out
    { from: clo, to: { ...clo, fx: clamp(cx + W * 0.05, 0, W) }, f: 30, shake: 6 }, //  5 close pan
  ];
  // Per-scene rhythm. Different seeds -> different editing feel.
  const PATTERNS = [
    [0, 2, 3], [1, 3, 2], [2, 0, 3, 5], [0, 3, 2], [1, 5, 3, 0], [3, 2, 1], [0, 2, 5, 3],
  ];
  const pat = PATTERNS[seed % PATTERNS.length];

  const shots: Shot[] = [];
  let t = 0;
  let i = 0;
  while (t < total - 3) {
    const m = MOVES[pat[i % pat.length]];
    const dur = Math.min(m.f, total - t);
    shots.push({ start: t, dur, from: m.from, to: m.to, shake: m.shake });
    t += dur;
    i++;
  }
  if (!shots.length) shots.push({ start: 0, dur: total, from: MOVES[0].from, to: MOVES[0].to, shake: 0 });
  return shots;
}

export const Camera: React.FC<{
  rect?: Rect;
  seed: number;
  sceneDur: number;
  children: React.ReactNode;
}> = ({ rect, seed, sceneDur, children }) => {
  const frame = useCurrentFrame();
  const { width: W, height: H, fps } = useVideoConfig();
  const shots = useMemo(() => buildShots(sceneDur, W, H, rect, seed), [sceneDur, W, H, rect, seed]);

  // A whoosh marks each hard cut: every internal framing change, plus the cut
  // INTO this scene (only for scenes after the first — seed > 0). Alternating two
  // swishes (one reversed) keeps repeated cuts from sounding identical.
  const cuts = shots.map((s) => s.start).filter((_, i) => i > 0 || seed > 0);
  const whooshLen = Math.ceil(0.5 * fps);

  let shot = shots[shots.length - 1];
  for (const s of shots) {
    if (frame >= s.start && frame < s.start + s.dur) {
      shot = s;
      break;
    }
  }
  const into = frame - shot.start;
  const p = interpolate(into, [0, shot.dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.cubic),
  });
  const scale = lerp(shot.from.scale, shot.to.scale, p);
  const fx = lerp(shot.from.fx, shot.to.fx, p);
  const fy = lerp(shot.from.fy, shot.to.fy, p);

  // Map world focal point (fx,fy) to screen center, then clamp inside the world
  // so a zoom never reveals black edges.
  let tx = clamp(W / 2 - fx * scale, W - W * scale, 0);
  let ty = clamp(H / 2 - fy * scale, H - H * scale, 0);

  // Impact shake on the first few frames of each cut — sells the hard cut.
  const amp = shot.shake * Math.max(0, 1 - into / 6);
  tx += Math.sin(into * 2.4) * amp;
  ty += Math.cos(into * 1.8) * amp;

  return (
    <AbsoluteFill style={{ overflow: "hidden", backgroundColor: "#000" }}>
      <div
        style={{
          position: "absolute",
          width: W,
          height: H,
          transformOrigin: "0 0",
          transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
          filter: "saturate(1.22) contrast(1.07)",
        }}
      >
        {children}
      </div>
      {cuts.map((cf, i) => (
        <Sequence key={`whoosh-${cf}`} from={cf} durationInFrames={whooshLen} name="whoosh">
          <Audio src={staticFile(i % 2 === 0 ? "sfx/whoosh1.wav" : "sfx/whoosh2.wav")} volume={0.5} />
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
