// Deterministic composition math shared by the Node render driver (render.mjs)
// and the browser runtime. buildShots() is the camera choreography (ported
// verbatim from the old Camera.tsx); computeComposition() derives, from a
// manifest, the per-scene shot arrays (shipped to the browser as window.__SHOTS)
// and the full static <audio> list (narration + whoosh SFX + music) that
// render.mjs writes into index.html so HyperFrames can mux it.

export function buildShots(total, W, H, rect, seed) {
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const cx = rect ? rect.x + rect.width / 2 : W / 2;
  const faceY = rect ? rect.y + rect.height * 0.33 : H * 0.36;
  const bodyY = rect ? rect.y + rect.height * 0.52 : H * 0.5;
  const est = { scale: 1.07, fx: W / 2, fy: H * 0.46 };
  const med = { scale: 1.4, fx: cx, fy: bodyY };
  const clo = { scale: 1.92, fx: cx, fy: faceY };
  const MOVES = [
    { from: { ...est, scale: 1.05 }, to: { ...est, scale: 1.17 }, f: 46, shake: 0 },
    { from: med, to: { ...med, scale: 1.48 }, f: 36, shake: 5 },
    { from: { ...clo, scale: 1.66 }, to: clo, f: 32, shake: 9 },
    { from: { ...clo, scale: 2.05 }, to: { ...clo, scale: 1.9 }, f: 22, shake: 14 },
    { from: { ...med, scale: 1.62 }, to: est, f: 40, shake: 4 },
    { from: clo, to: { ...clo, fx: clamp(cx + W * 0.05, 0, W) }, f: 30, shake: 6 },
  ];
  const PATTERNS = [
    [0, 2, 3], [1, 3, 2], [2, 0, 3, 5], [0, 3, 2], [1, 5, 3, 0], [3, 2, 1], [0, 2, 5, 3],
  ];
  const pat = PATTERNS[seed % PATTERNS.length];
  const shots = [];
  let t = 0, i = 0;
  while (t < total - 3) {
    const m = MOVES[pat[i % pat.length]];
    const dur = Math.min(m.f, total - t);
    shots.push({ start: t, dur, from: m.from, to: m.to, shake: m.shake });
    t += dur; i++;
  }
  if (!shots.length) shots.push({ start: 0, dur: total, from: MOVES[0].from, to: MOVES[0].to, shake: 0 });
  return shots;
}

// Given a manifest, return { totalFrames, shotsByScene, audios }.
//   shotsByScene[i]  camera shots for scene i (null for transformation scenes)
//   audios           [{ src, start(sec), duration(sec), volume, track }]
export function computeComposition(manifest) {
  const FPS = manifest.fps || 30;
  const W = manifest.width, H = manifest.height;
  const audios = [];
  const shotsByScene = [];
  let whooshIdx = 0;
  let startFrame = 0;

  manifest.scenes.forEach((scene, index) => {
    const durFrames = scene.durationInFrames;
    const startSec = startFrame / FPS;
    const durSec = durFrames / FPS;

    if (scene.kind === "transformation" && scene.panels) {
      shotsByScene.push(null);
    } else {
      const focus = scene.characters && scene.characters[0] ? scene.characters[0].rect : undefined;
      const shots = buildShots(durFrames, W, H, focus, index);
      shotsByScene.push(shots);
      // A whoosh marks each hard cut: every internal framing change plus the cut
      // INTO this scene (scenes after the first — index > 0).
      const cutFrames = shots.map((s) => s.start).filter((_, i) => i > 0 || index > 0);
      cutFrames.forEach((cf, i) => {
        audios.push({
          src: i % 2 === 0 ? "sfx/whoosh1.wav" : "sfx/whoosh2.wav",
          start: startSec + cf / FPS, duration: 0.5, volume: 0.5,
          track: 20 + (whooshIdx++ % 8),
        });
      });
    }

    if (scene.audio) {
      audios.push({ src: scene.audio, start: startSec, duration: durSec, volume: 1, track: 10 });
    }
    startFrame += durFrames;
  });

  if (manifest.music && manifest.music.src) {
    const gainDb = manifest.music.gainDb != null ? manifest.music.gainDb : -22;
    audios.push({
      src: manifest.music.src, start: 0, duration: startFrame / FPS,
      volume: Math.pow(10, gainDb / 20), track: 30,
    });
  }

  return { totalFrames: Math.max(1, startFrame), shotsByScene, audios };
}
