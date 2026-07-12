// Phase-0 spike builder: transcribe the KittenTTS narration with whisper.cpp,
// then assemble src/spike-manifest.json (3 wojak-style cat-story scenes).
import {
  installWhisperCpp,
  downloadWhisperModel,
  transcribe,
  toCaptions,
} from "@remotion/install-whisper-cpp";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REMOTION = path.resolve(__dirname, "..");
const REPO = path.resolve(REMOTION, "..");
const WHISPER_DIR = path.join(REMOTION, "whisper.cpp");
const AUDIO = path.join(REPO, "work", "audio", "spike");
const WHISPER_VERSION = "1.7.4";
const MODEL = "base.en";
const FPS = 30;

const meta = JSON.parse(readFileSync(path.join(AUDIO, "meta.json"), "utf8"));
const seqCount = readdirSync(path.join(REPO, "work", "seq", "002")).filter((f) =>
  f.endsWith(".png"),
).length;

console.log("Installing whisper.cpp", WHISPER_VERSION, "->", WHISPER_DIR);
await installWhisperCpp({ version: WHISPER_VERSION, to: WHISPER_DIR, printOutput: true });
console.log("Downloading model", MODEL);
await downloadWhisperModel({ model: MODEL, folder: WHISPER_DIR, printOutput: true });

async function tokensFor(sceneId) {
  const wav = path.join(AUDIO, `${sceneId}.wav`);
  const wav16 = path.join(AUDIO, `${sceneId}.16k.wav`);
  execFileSync("ffmpeg", ["-y", "-nostdin", "-i", wav, "-ar", "16000", "-ac", "1", wav16], {
    stdio: "ignore",
  });
  const out = await transcribe({
    inputPath: wav16,
    whisperPath: WHISPER_DIR,
    whisperCppVersion: WHISPER_VERSION,
    model: MODEL,
    modelFolder: WHISPER_DIR,
    tokenLevelTimestamps: true,
  });
  const { captions } = toCaptions({ whisperCppOutput: out });
  return captions
    .map((c) => ({ text: c.text.trim(), startMs: c.startMs, endMs: c.endMs }))
    .filter((t) => t.text.length > 0);
}

const FULL = { x: 0, y: 0, width: 1920, height: 1080 };
const defs = [
  {
    id: "s1",
    bg: { kind: "flat", color: "#3b2f28", color2: "#1a1410" },
    char: { id: "003", kind: "sprite", src: "sprites/003.png", rect: FULL, enter: "pop" },
  },
  {
    id: "s2",
    bg: { kind: "themed", src: "bg/kitchen.jpg" },
    caption: '*knocked the WHOLE bag off the counter*',
    char: {
      id: "002",
      kind: "animated",
      src: "seq/002",
      seqCount,
      seqFps: 20,
      rect: FULL,
      enter: "pop",
    },
  },
  {
    id: "s3",
    bg: { kind: "flat", color: "#26313d", color2: "#10151b" },
    char: { id: "008", kind: "sprite", src: "sprites/008.png", rect: FULL, enter: "slideRight" },
  },
];

const scenes = [];
for (const d of defs) {
  const tokens = await tokensFor(d.id);
  const durSec = (meta.durations[d.id] ?? 4) + 0.45; // small tail
  scenes.push({
    id: d.id,
    durationInFrames: Math.round(durSec * FPS),
    audio: `audio/spike/${d.id}.wav`,
    background: d.bg,
    caption: d.caption,
    characters: [d.char],
    tokens,
    transition: "fade",
  });
  console.log(`${d.id}: ${tokens.length} tokens, ${Math.round(durSec * FPS)} frames`);
}

const manifest = { id: "spike", fps: FPS, width: 1920, height: 1080, assetsBase: "", scenes };
const outPath = path.join(REMOTION, "src", "spike-manifest.json");
writeFileSync(outPath, JSON.stringify(manifest, null, 2) + "\n");
console.log("Wrote", outPath);
console.log("Total frames:", scenes.reduce((a, s) => a + s.durationInFrames, 0));
