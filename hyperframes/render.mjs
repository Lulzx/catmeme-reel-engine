// Render a saga manifest locally with HyperFrames (no cloud) — the replacement
// for the old remotion/scripts/render-local.mjs.
//   node hyperframes/render.mjs <manifest.json> [out.mp4]
//
// Scaffolds a self-contained HyperFrames project under work/hf/<id>/ (index.html
// that inlines the manifest + vendored GSAP + runtime.js, with the asset dirs
// symlinked in exactly as remotion/public/ used to map them), then runs
// `npx hyperframes render`. HyperFrames owns audio playback and muxes the
// <audio> elements into the MP4.
import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, rmSync, mkdirSync, symlinkSync, copyFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { computeComposition } from "./shots.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HF = __dirname;                       // hyperframes/
const REPO = path.resolve(HF, "..");

const manifestArg = process.argv[2];
const outArg = process.argv[3];
if (!manifestArg) {
  console.error("usage: node hyperframes/render.mjs <manifest.json> [out.mp4]");
  process.exit(1);
}

const manifestPath = path.resolve(manifestArg);
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const out = outArg ? path.resolve(outArg) : path.join(REPO, "output", `${manifest.id}.mp4`);
mkdirSync(path.dirname(out), { recursive: true });

const buildDir = path.join(REPO, "work", "hf", manifest.id);
rmSync(buildDir, { recursive: true, force: true });
mkdirSync(buildDir, { recursive: true });

// Asset dirs, mirroring the old remotion/public/ symlinks so manifest-relative
// paths (sprites/…, bg/…, audio/…, seq/…, sfx/…) resolve inside the build dir.
const ASSET_LINKS = {
  sprites: path.join(REPO, "work", "sprites"),
  audio: path.join(REPO, "work", "audio"),
  seq: path.join(REPO, "work", "seq"),
  bg: path.join(REPO, "backgrounds"),
  sfx: path.join(HF, "sfx"),
};
for (const [name, target] of Object.entries(ASSET_LINKS)) {
  if (existsSync(target)) symlinkSync(target, path.join(buildDir, name), "dir");
}

// Vendored GSAP (copied so the build dir is self-contained). runtime.js is
// inlined into index.html below so the HyperFrames static linter can see the
// window.__timelines registration (it only scans index.html, not linked JS).
copyFileSync(path.join(HF, "vendor", "gsap.min.js"), path.join(buildDir, "gsap.min.js"));
const runtimeJs = readFileSync(path.join(HF, "runtime.js"), "utf8");

// Optional background music: HyperFrames has no runtime loop, so bake a loop to
// the full composition length here and repoint the manifest at the local file.
// (Do this BEFORE computeComposition so the audio list points at the local file.)
const fps = manifest.fps || 30;
const totalFrames = Math.max(1, manifest.scenes.reduce((a, s) => a + s.durationInFrames, 0));
if (manifest.music && manifest.music.src) {
  const srcAbs = path.isAbsolute(manifest.music.src)
    ? manifest.music.src
    : path.join(REPO, manifest.music.src);
  if (existsSync(srcAbs)) {
    const looped = path.join(buildDir, "bgm.m4a");
    await run("ffmpeg", ["-y", "-stream_loop", "-1", "-i", srcAbs, "-t",
      String(totalFrames / fps), "-c:a", "aac", "-b:a", "160k", looped], { quiet: true });
    manifest.music = { ...manifest.music, src: "bgm.m4a" };
  } else {
    console.warn(`  music src not found (${srcAbs}); skipping BGM`);
    delete manifest.music;
  }
}

// Camera shots (-> window.__SHOTS for the runtime) and the static <audio> list.
const { shotsByScene, audios } = computeComposition(manifest);
const audioTags = audios.map((a, i) =>
  `<audio id="audio-${i}" src="${a.src}"` +
  ` data-start="${a.start.toFixed(4)}" data-duration="${a.duration.toFixed(4)}"` +
  ` data-track-index="${a.track}" data-volume="${a.volume}"></audio>`
).join("\n      ");

const totalSec = (totalFrames / fps).toFixed(4);
const W = manifest.width, H = manifest.height;

const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=${W}, height=${H}" />
    <script src="gsap.min.js"></script>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      html, body { width: ${W}px; height: ${H}px; overflow: hidden; background: #000; }
    </style>
  </head>
  <body>
    <div id="stage"
         data-composition-id="${manifest.id}"
         data-start="0"
         data-duration="${totalSec}"
         data-fps="${fps}"
         data-width="${W}"
         data-height="${H}">
      ${audioTags}
    </div>
    <script>window.__MANIFEST = ${JSON.stringify(manifest)};</script>
    <script>window.__SHOTS = ${JSON.stringify(shotsByScene)};</script>
    <script>${runtimeJs}</script>
  </body>
</html>
`;
writeFileSync(path.join(buildDir, "index.html"), html);

console.log(`Scaffolded HyperFrames project at ${path.relative(REPO, buildDir)}`);
if (process.env.HF_SCAFFOLD_ONLY) {
  console.log("scaffold-only: skipping render");
  process.exit(0);
}
console.log(`Rendering "${manifest.id}" — ${totalFrames} frames @ ${fps}fps -> ${path.relative(REPO, out)}`);

await run("npx", ["hyperframes", "render", buildDir, "--output", out, "--fps", String(fps)]);
if (!existsSync(out)) {
  console.error(`render reported done but ${out} is missing`);
  process.exit(1);
}
console.log("\nDone:", out);

function run(cmd, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, {
      cwd: REPO,
      stdio: opts.quiet ? ["ignore", "ignore", "inherit"] : "inherit",
    });
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0 ? resolve() : reject(new Error(`${cmd} exited ${code}`)));
  });
}
