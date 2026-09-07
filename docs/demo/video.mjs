/**
 * Build the submission video from the committed stills and diagrams.
 *
 * The cut is defined in `docs/hackathon-build/demo-plan.md`; this is that plan
 * as something that renders.
 *
 * Three things happen per shot:
 *   1. `frame` crops the still to the region the shot is about, so a dense
 *      screenshot arrives legible instead of arriving whole and small.
 *   2. `focus` dims everything outside one or more rectangles and rules them in
 *      gold, so the narration and the eye land on the same pixels.
 *   3. `vo` is spoken by Gemini TTS on Vertex AI and laid under the shot; the
 *      shot is held for at least as long as the line takes. Captions stay burned
 *      in — a judging page often plays muted.
 *
 * All rectangles are normalized to the SOURCE image: [x, y, w, h] in 0–1.
 *
 *   node docs/demo/video.mjs [--url https://…] [--out path.mp4] [--silent]
 *
 * Needs ffmpeg, a global playwright, and gcloud logged in to a project with
 * Vertex AI enabled.
 */
import { chromium } from "/opt/homebrew/lib/node_modules/playwright/index.mjs";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, renameSync, writeFileSync } from "node:fs";

const ROOT = "/Users/hanyu/dev/sourcecut";
const SHOTS = `${ROOT}/docs/demo/shots`;
const DIAGRAMS = `${ROOT}/docs/diagrams`;
const WORK = "/private/tmp/claude-501/-Users-hanyu-dev-sourcecut/5fea0b69-e7d5-4601-815e-537d91088d43/scratchpad/video";
const VOICE_CACHE = `${WORK}/../voice-cache`;

const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : fallback;
};
const HOSTED_URL = arg("--url", "");
const OUT = arg("--out", `${ROOT}/output/sourcecut-demo.mp4`);
const SILENT = args.includes("--silent");

const WIDTH = 1920;
const HEIGHT = 1080;
const FPS = 25;
const GROUND = "0x0b0f14";
const GOLD = "0xe0a96d";

// The caption is read first, so it sits at the top and the still takes the rest
// of the frame. The band is measured once from the tallest caption and then
// applied to every shot, so the plate never shifts between cuts and nothing the
// narration points at can end up underneath the type.
let PLATE = { x: 30, y: 260, w: 1860, h: 800 };

// Vertex AI, project as configured for the rest of the app.
const TTS_PROJECT = process.env.GOOGLE_CLOUD_PROJECT || "sourcecut-64338";
const TTS_LOCATION = "us-central1";
const TTS_MODEL = "gemini-2.5-flash-preview-tts";
const TTS_VOICE = "Charon";
const LEAD_IN = 0.5;   // silence before the line starts
const TAIL = 0.8;      // silence held after it ends

/** The cut. `seconds` is the floor; a longer narration line extends the shot. */
const CUT = [
  {
    asset: `${SHOTS}/01-landing-hero.png`,
    seconds: 12,
    focus: [[0.06, 0.125, 0.45, 0.33]],
    caption: "Films set in the past have to get the small things right.",
    sub: "The answers sit in what people wrote at the time — diaries, letters, poems.",
    vo: "Getting the past right means small things: the food, the tools, the weather that day. The answers sit in what people wrote at the time — diaries, letters, poems. SourceCut finds them, and shows the lines.",
  },
  {
    asset: `${SHOTS}/03-corpus-cards.png`,
    seconds: 8,
    focus: [[0.016, 0.66, 0.44, 0.13], [0.518, 0.66, 0.44, 0.13]],
    caption: "The pipeline isn't built around diaries.",
    sub: "Any collection of primary sources runs the same five steps.",
    vo: "The pipeline is not built around diaries. Any collection of primary sources runs the same five steps, and the two loaded here were picked because they are nothing alike.",
  },
  {
    asset: `${SHOTS}/05-brief-typed.png`,
    seconds: 8,
    frame: [0.185, 0.005, 0.815, 0.575],
    focus: [[0.214, 0.398, 0.759, 0.109]],
    caption: "Type what your scene needs, in ordinary words.",
    sub: "The answer is built only from what the diaries say.",
    vo: "Type what your scene needs, in ordinary words. The answer is built only from what the diaries say.",
  },
  {
    asset: `${DIAGRAMS}/p1-planning.png`,
    seconds: 11,
    caption: "Gemini turns that into a plan.",
    sub: "Which dates to search, and which old spellings to try.",
    vo: "Gemini turns that into a plan: which dates to search, and which old spellings to try.",
  },
  {
    asset: `${SHOTS}/41-trace-plan.png`,
    seconds: 8,
    frame: [0.055, 0.14, 0.895, 0.175],
    focus: [[0.058, 0.263, 0.88, 0.045]],
    caption: "A real run: five things to find, over six weeks in 1805.",
    sub: "The first search finds none of them.",
    vo: "A real run: five things to find, over six weeks in 1805. The first search finds none.",
  },
  {
    asset: `${DIAGRAMS}/p2-coverage-rounds.png`,
    seconds: 10,
    caption: "Each item has its own test for being found,",
    sub: "so the tool knows which ones are still missing.",
    vo: "Each item has its own test for being found, so the tool knows which ones are still missing.",
  },
  {
    asset: `${SHOTS}/43-trace-gap-replan.png`,
    seconds: 10,
    frame: [0.055, 0.308, 0.895, 0.252],
    focus: [[0.155, 0.365, 0.72, 0.185]],
    caption: "So it tries the words people actually wrote in 1805 —",
    sub: "ironboat, sward, vapour. Now it finds four of the five.",
    vo: "So it tries the words people wrote in 1805 — ironboat, sward, vapour — and finds four of the five.",
  },
  {
    asset: `${DIAGRAMS}/p3-specialist-agents.png`,
    seconds: 12,
    caption: "Three agents on Google's Agent Development Kit:",
    sub: "one plans, one searches, one checks. Only the searcher touches the database.",
    vo: "Three agents on Google's Agent Development Kit: one plans, one searches, one checks. Only the searcher touches the database.",
  },
  {
    asset: `${SHOTS}/45-trace-sql.png`,
    seconds: 9,
    caption: "Every search is read-only SQL through ClickHouse's own MCP server.",
    sub: "The agent can read the texts, and nothing else.",
    vo: "Every search is read-only SQL through ClickHouse's own MCP server. The agent can read the texts and nothing else.",
  },
  {
    asset: `${DIAGRAMS}/01-system-topology.png`,
    seconds: 11,
    caption: "The texts, the search index, and a log of every step",
    sub: "all live in ClickHouse.",
    vo: "The texts, the search index and a log of every step all live in ClickHouse.",
  },
  {
    asset: `${SHOTS}/13-timeline-date-held.png`,
    seconds: 8,
    frame: [0.19, 0.15, 0.81, 0.368],
    focus: [[0.2, 0.245, 0.78, 0.14]],
    caption: "The result opens on a calendar:",
    sub: "every day, and how much of your scene the diaries back up.",
    vo: "The result opens on a calendar: every day, and how much of your scene the diaries back up.",
  },
  {
    asset: `${SHOTS}/21-requirement-panel.png`,
    seconds: 9,
    frame: [0.01, 0.11, 0.98, 0.58],
    focus: [[0.634, 0.224, 0.33, 0.165]],
    caption: "Open an item to read the quotes,",
    sub: "and to see which of the three men wrote it, on which day.",
    vo: "Open an item to read the quotes, and see which of the three men wrote it, on which day.",
  },
  {
    asset: `${SHOTS}/24-passage-span.png`,
    seconds: 8,
    frame: [0.05, 0.16, 0.91, 0.63],
    focus: [[0.085, 0.312, 0.83, 0.108], [0.06, 0.572, 0.21, 0.07]],
    caption: "Click a quote for the whole diary entry it came from,",
    sub: "with the quoted words marked in it. Nothing is paraphrased.",
    vo: "Click a quote for the whole diary entry, with the quoted words marked. Nothing is paraphrased.",
  },
  {
    asset: `${SHOTS}/31-reference-rights.png`,
    seconds: 7,
    frame: [0.557, 0.02, 0.434, 0.58],
    focus: [[0.575, 0.195, 0.41, 0.055], [0.575, 0.335, 0.41, 0.05]],
    caption: "Old pictures come with their paperwork.",
    sub: "Where it is from, its catalogue number, and whether you can use it.",
    vo: "Old pictures come with their source, their catalogue number, and whether you can use them.",
  },
  {
    asset: `${SHOTS}/50-unmet-requirement.png`,
    seconds: 9,
    caption: "When the diaries say nothing, it says so.",
    sub: "The iron boat is in the history books, not in these three diaries.",
    vo: "When the diaries say nothing, it says so. The iron boat is in the history books, not in these three diaries.",
  },
  {
    asset: `${SHOTS}/06-project-odyssey.png`,
    seconds: 9,
    frame: [0.185, 0.0, 0.815, 0.62],
    focus: [[0.2, 0.198, 0.475, 0.075], [0.198, 0.315, 0.45, 0.055]],
    caption: "Same five steps, a completely different text.",
    sub: "The Odyssey has no dates, so it is searched by book and line instead.",
    vo: "Here is that on a poem. The Odyssey has no dates, so it is searched by book and line instead — same five steps, same evidence rules.",
  },
  {
    asset: `${SHOTS}/02-landing-full.png`,
    seconds: 6,
    caption: "SourceCut — scene research from the original sources, with the proof attached.",
    sub: HOSTED_URL,
    vo: "SourceCut. Scene research from the original sources, with the proof attached.",
  },
];

mkdirSync(WORK, { recursive: true });
mkdirSync(VOICE_CACHE, { recursive: true });
mkdirSync(`${ROOT}/output`, { recursive: true });

const ffmpeg = (params) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...params]);
const probeDuration = (file) =>
  Number(
    execFileSync("ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", file])
      .toString()
      .trim(),
  );
const probeSize = (file) => {
  const [w, h] = execFileSync("ffprobe", [
    "-v", "error", "-select_streams", "v:0",
    "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", file,
  ]).toString().trim().split("x").map(Number);
  return { w, h };
};

// ── narration ───────────────────────────────────────────────────────────────
// The model's pace wanders between takes — the same line has come back at 1.8
// and at 4.7 words a second. Too slow eats the three-minute budget, too fast
// sounds hurried over a frame someone is still reading, so each line is spoken
// until a take lands in the band, and the closest one is kept.
const PACE_MIN = 2.1;
const PACE_MAX = 3.1;
const PACE_IDEAL = 2.5;
const PACE_ATTEMPTS = 3;

if (!SILENT) {
  const token = execFileSync("gcloud", ["auth", "print-access-token"]).toString().trim();
  const endpoint =
    `https://${TTS_LOCATION}-aiplatform.googleapis.com/v1/projects/${TTS_PROJECT}` +
    `/locations/${TTS_LOCATION}/publishers/google/models/${TTS_MODEL}:generateContent`;
  // Trim the model's own lead-in and trailing silence; the cut adds its own.
  const trim =
    "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05:" +
    "stop_periods=-1:stop_threshold=-50dB:stop_silence=0.35";

  const speak = async (text, destination) => {
    const body = {
      contents: [{ role: "user", parts: [{ text }] }],
      generationConfig: {
        responseModalities: ["AUDIO"],
        speechConfig: { voiceConfig: { prebuiltVoiceConfig: { voiceName: TTS_VOICE } } },
      },
    };
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) throw new Error(`TTS ${response.status}: ${await response.text()}`);
    const payload = await response.json();
    const parts = payload.candidates?.[0]?.content?.parts ?? [];
    const pcm = Buffer.concat(
      parts.filter((part) => part.inlineData?.data).map((part) => Buffer.from(part.inlineData.data, "base64")),
    );
    if (pcm.length === 0) throw new Error(`TTS returned no audio for: ${text.slice(0, 60)}…`);
    const raw = `${destination}.pcm`;
    writeFileSync(raw, pcm);
    // The model answers as headerless 24 kHz mono signed 16-bit PCM.
    ffmpeg([
      "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", raw,
      "-af", trim, "-ar", "48000", "-ac", "2", destination,
    ]);
    return probeDuration(destination);
  };

  for (const shot of CUT) {
    if (!shot.vo) continue;
    const words = shot.vo.split(/\s+/).length;
    const key = createHash("sha1").update(`${TTS_VOICE}|${shot.vo}`).digest("hex").slice(0, 16);
    shot.voice = `${VOICE_CACHE}/${key}.wav`;

    if (!existsSync(shot.voice)) {
      let best = null;
      for (let attempt = 1; attempt <= PACE_ATTEMPTS; attempt += 1) {
        const candidate = `${VOICE_CACHE}/${key}.take${attempt}.wav`;
        const seconds = await speak(shot.vo, candidate);
        const pace = words / seconds;
        const distance = Math.abs(pace - PACE_IDEAL);
        if (!best || distance < best.distance) best = { candidate, seconds, pace, distance };
        if (pace >= PACE_MIN && pace <= PACE_MAX) break;
        console.warn(`  ${pace.toFixed(1)} words/s on take ${attempt}, speaking it again`);
      }
      renameSync(best.candidate, shot.voice);
    }

    shot.voiceSeconds = probeDuration(shot.voice);
    shot.pace = words / shot.voiceSeconds;
    shot.seconds = Math.max(shot.seconds, Math.ceil((shot.voiceSeconds + LEAD_IN + TAIL) * 2) / 2);
  }
}

const total = CUT.reduce((sum, shot) => sum + shot.seconds, 0);
console.log(`cut: ${CUT.length} shots, ${total}s (${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")})`);
for (const shot of CUT) {
  const spoken = shot.voiceSeconds
    ? `${shot.voiceSeconds.toFixed(1)}s spoken · ${shot.pace.toFixed(1)} w/s`
    : "silent";
  console.log(`  ${String(shot.seconds).padStart(2)}s  ${spoken.padStart(12)}  ${shot.asset.split("/").pop()}`);
}
if (total > 175) throw new Error(`Cut runs ${total}s; the rules cap the video at 180s`);

// ── captions, rendered in the product's own type ────────────────────────────
const CAPTION_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,300;6..72,400&family=Inter:wght@400;500&display=swap');
  html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; background: transparent; }
  .bar { position: absolute; left: 0; right: 0; top: 0; box-sizing: border-box;
         padding: 54px 96px 40px;
         background: linear-gradient(to bottom, rgba(8,11,14,0.97) 55%, rgba(8,11,14,0.86) 80%, rgba(8,11,14,0)); }
  .rule { width: 64px; height: 3px; background: #e0a96d; margin-bottom: 22px; }
  h1 { margin: 0; font-family: Newsreader, Georgia, serif; font-weight: 400; font-size: 46px;
       line-height: 1.22; color: #f1f5f9; letter-spacing: -0.01em; }
  p { margin: 12px 0 0; font-family: Inter, system-ui, sans-serif; font-size: 30px; line-height: 1.35; color: #94a3b8; }
  p.url { font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 26px; color: #e0a96d; letter-spacing: 0.04em; }
`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: WIDTH, height: HEIGHT } });
for (const [index, shot] of CUT.entries()) {
  const isUrl = shot.sub && /^https?:/.test(shot.sub);
  await page.setContent(
    `<style>${CAPTION_CSS}</style><div class="bar"><div class="rule"></div>` +
      `<h1>${shot.caption}</h1>` +
      (shot.sub ? `<p class="${isUrl ? "url" : ""}">${shot.sub}</p>` : "") +
      `</div>`,
    { waitUntil: "networkidle" },
  );
  shot.caption_png = `${WORK}/caption-${String(index).padStart(2, "0")}.png`;
  shot.captionHeight = await page.evaluate(() => document.querySelector(".bar").offsetHeight);
  await page.screenshot({ path: shot.caption_png, omitBackground: true });
}
await browser.close();

const band = Math.max(...CUT.map((shot) => shot.captionHeight));
PLATE = { x: 30, y: band + 16, w: 1860, h: HEIGHT - band - 44 };
console.log(`captions rendered · band ${band}px · plate ${PLATE.w}x${PLATE.h} at y=${PLATE.y}`);

// ── segments ────────────────────────────────────────────────────────────────
/** Source rect (normalized) to a whole-pixel crop, clamped to the image. */
const cropRect = (size, [x, y, w, h]) => {
  const cx = Math.max(0, Math.round(x * size.w));
  const cy = Math.max(0, Math.round(y * size.h));
  return {
    x: cx,
    y: cy,
    w: Math.min(size.w - cx, Math.round(w * size.w)),
    h: Math.min(size.h - cy, Math.round(h * size.h)),
  };
};

CUT.forEach((shot, index) => {
  shot.segment = `${WORK}/segment-${String(index).padStart(2, "0")}.mp4`;
  const size = probeSize(shot.asset);
  const frame = shot.frame ? cropRect(size, shot.frame) : { x: 0, y: 0, w: size.w, h: size.h };

  // The plate: the frame scaled to fit, then placed in the top region so the
  // caption never covers what the narration is pointing at.
  const scale = Math.min(PLATE.w / frame.w, PLATE.h / frame.h);
  const plateW = Math.round((frame.w * scale) / 2) * 2;
  const plateH = Math.round((frame.h * scale) / 2) * 2;
  const plateX = PLATE.x + Math.round((PLATE.w - plateW) / 2);
  const plateY = PLATE.y + Math.round((PLATE.h - plateH) / 2);

  const steps = [
    `[0:v]crop=${frame.w}:${frame.h}:${frame.x}:${frame.y},scale=${plateW}:${plateH}:flags=lanczos[plate]`,
  ];
  let plate = "plate";

  // Spotlight: dim the plate, paste the focused rectangles back at full
  // strength, then rule each one in gold.
  if (shot.focus?.length) {
    // One copy of the plate to dim, plus one per rectangle to crop from.
    const copies = shot.focus.map((_, n) => `[src${n}]`).join("");
    steps.push(`[plate]split=${shot.focus.length + 1}[toDim]${copies}`);
    steps.push(`[toDim]eq=brightness=-0.26:saturation=0.45[dim]`);
    let base = "dim";
    shot.focus.forEach((rect, n) => {
      // The rectangle is given in source coordinates; move it into the plate.
      const r = cropRect(size, rect);
      const x = Math.max(0, Math.round((r.x - frame.x) * scale));
      const y = Math.max(0, Math.round((r.y - frame.y) * scale));
      const w = Math.min(plateW - x, Math.round(r.w * scale));
      const h = Math.min(plateH - y, Math.round(r.h * scale));
      if (w <= 0 || h <= 0) throw new Error(`focus rect ${n} of ${shot.asset} falls outside the frame`);
      steps.push(`[src${n}]crop=${w}:${h}:${x}:${y}[cut${n}]`);
      steps.push(`[${base}][cut${n}]overlay=${x}:${y}[lit${n}]`);
      steps.push(`[lit${n}]drawbox=x=${x}:y=${y}:w=${w}:h=${h}:color=${GOLD}@0.9:t=3[box${n}]`);
      base = `box${n}`;
    });
    plate = base;
  }

  steps.push(`color=c=${GROUND}:s=${WIDTH}x${HEIGHT}:d=${shot.seconds}:r=${FPS}[ground]`);
  steps.push(`[ground][${plate}]overlay=${plateX}:${plateY}[framed]`);
  steps.push(`[framed][1:v]overlay=0:0:format=auto,format=yuv420p[v]`);

  const inputs = ["-loop", "1", "-i", shot.asset, "-loop", "1", "-i", shot.caption_png];
  const map = ["-map", "[v]"];
  if (shot.voice) {
    inputs.push("-i", shot.voice);
    steps.push(`[2:a]adelay=${Math.round(LEAD_IN * 1000)}:all=1,apad[a]`);
    map.push("-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2");
  } else {
    inputs.push("-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000");
    map.push("-map", "2:a", "-c:a", "aac", "-b:a", "160k");
  }

  ffmpeg([
    ...inputs,
    "-filter_complex", steps.join(";"),
    ...map,
    "-t", String(shot.seconds),
    "-r", String(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
    shot.segment,
  ]);
  console.log(`  segment ${index + 1}/${CUT.length} · ${shot.seconds}s · ${shot.asset.split("/").pop()}`);
});

const list = `${WORK}/segments.txt`;
writeFileSync(list, CUT.map((shot) => `file '${shot.segment}'`).join("\n"), "utf8");
ffmpeg(["-f", "concat", "-safe", "0", "-i", list, "-c", "copy", "-movflags", "+faststart", OUT]);

const probe = execFileSync("ffprobe", [
  "-v", "error", "-show_entries", "format=duration,size", "-of", "default=nw=1", OUT,
]).toString().trim();
console.log(`\n${OUT}\n${probe}`);
