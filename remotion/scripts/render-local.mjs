// Render a story manifest locally with Remotion (no cloud).
//   node scripts/render-local.mjs [manifest.json] [out.mp4]
// Defaults to src/spike-manifest.json -> ../output/<id>.mp4
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REMOTION = path.resolve(__dirname, "..");
const REPO = path.resolve(REMOTION, "..");

const manifestArg = process.argv[2];
const outArg = process.argv[3];

const manifestPath = manifestArg
  ? path.resolve(manifestArg)
  : path.join(REMOTION, "src", "spike-manifest.json");
const inputProps = JSON.parse(readFileSync(manifestPath, "utf8"));
const out = outArg ? path.resolve(outArg) : path.join(REPO, "output", `${inputProps.id}.mp4`);

console.log("Bundling Remotion project…");
const serveUrl = await bundle({
  entryPoint: path.join(REMOTION, "src", "index.ts"),
  publicDir: path.join(REMOTION, "public"),
});

const composition = await selectComposition({ serveUrl, id: "Story", inputProps });
console.log(`Rendering "${inputProps.id}" — ${composition.durationInFrames} frames @ ${composition.fps}fps -> ${out}`);

await renderMedia({
  serveUrl,
  composition,
  codec: "h264",
  outputLocation: out,
  inputProps,
  onProgress: ({ progress }) => process.stdout.write(`\r  ${(progress * 100).toFixed(1)}%   `),
});
console.log("\nDone:", out);
