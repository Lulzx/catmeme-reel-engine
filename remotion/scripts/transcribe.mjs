// Reusable whisper.cpp transcription for the caption pipeline.
//   node scripts/transcribe.mjs in.json out.json
// in.json:  [{ "id": "s1", "wav": "/abs/path/s1.16k.wav" }, ...]   (16kHz mono)
// out.json: { "s1": [{ "text", "startMs", "endMs" }], ... }
import {
  installWhisperCpp,
  downloadWhisperModel,
  transcribe,
  toCaptions,
} from "@remotion/install-whisper-cpp";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WHISPER_DIR = path.join(path.resolve(__dirname, ".."), "whisper.cpp");
const VERSION = "1.7.4";
const MODEL = "base.en";

const [, , inPath, outPath] = process.argv;
const items = JSON.parse(readFileSync(inPath, "utf8"));

await installWhisperCpp({ version: VERSION, to: WHISPER_DIR });
await downloadWhisperModel({ model: MODEL, folder: WHISPER_DIR });

const out = {};
for (const it of items) {
  const r = await transcribe({
    inputPath: it.wav,
    whisperPath: WHISPER_DIR,
    whisperCppVersion: VERSION,
    model: MODEL,
    modelFolder: WHISPER_DIR,
    tokenLevelTimestamps: true,
  });
  const { captions } = toCaptions({ whisperCppOutput: r });
  out[it.id] = captions
    .map((c) => ({ text: c.text.trim(), startMs: c.startMs, endMs: c.endMs }))
    .filter((t) => /[A-Za-z0-9]/.test(t.text));
}
writeFileSync(outPath, JSON.stringify(out, null, 2));
console.log("wrote", outPath);
