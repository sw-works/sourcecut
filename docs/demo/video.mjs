/**
 * Build the submission video from the committed stills and diagrams.
 *
 * The cut is defined in `docs/hackathon-build/demo-plan.md`; this is that plan
 * as something that renders. Captions are burned in rather than narrated: the
 * rules accept English subtitles, and a judging page usually plays muted.
 *
 * Each caption is rendered by the browser in the product's own typefaces, so
 * the lower third belongs to the same design as the frames above it, then
 * ffmpeg pads every still onto a 1920×1080 ground, adds a slow push, and
 * concatenates the segments.
 *
 *   node docs/demo/video.mjs [--url https://…] [--out path.mp4]
 *
 * Needs ffmpeg and a global playwright.
 */
import { chromium } from "/opt/homebrew/lib/node_modules/playwright/index.mjs";
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";

const ROOT = "/Users/hanyu/dev/sourcecut";
const SHOTS = `${ROOT}/docs/demo/shots`;
const DIAGRAMS = `${ROOT}/docs/diagrams`;
const WORK = "/private/tmp/claude-501/-Users-hanyu-dev-sourcecut/5fea0b69-e7d5-4601-815e-537d91088d43/scratchpad/video";

const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const index = args.indexOf(name);
  return index >= 0 ? args[index + 1] : fallback;
};
const HOSTED_URL = arg("--url", "");
const OUT = arg("--out", `${ROOT}/output/sourcecut-demo.mp4`);

const WIDTH = 1920;
const HEIGHT = 1080;
const FPS = 25;
const GROUND = "0x0b0f14";

/** The cut. Seconds are the plan's; the sum is checked before rendering. */
const CUT = [
  {
    asset: `${SHOTS}/01-landing-hero.png`,
    seconds: 10,
    caption: "A period film lives on detail. The Lewis and Clark journals hold it —",
    sub: "2,366 passages from three men who were there.",
  },
  {
    asset: `${SHOTS}/03-corpus-cards.png`,
    seconds: 8,
    caption: "Two corpora, one pipeline.",
    sub: "Pick a project; the journals and the poem are researched the same way.",
  },
  {
    asset: `${SHOTS}/05-brief-typed.png`,
    seconds: 8,
    caption: "Ask the way you'd brief an art department.",
    sub: "The Great Falls portage, the gear they built, the ground they hauled across.",
  },
  {
    asset: `${DIAGRAMS}/p1-planning.png`,
    seconds: 13,
    caption: "Gemini plans the research: which stretch, which requirements, which period words.",
    sub: "The date window is read from a curated file of expedition segments.",
    light: true,
  },
  {
    asset: `${SHOTS}/41-trace-plan.png`,
    seconds: 11,
    caption: "Five requirements over the Great Falls window. The first pass comes back thin —",
    sub: "zero of five. Every step of the run is itself a row in ClickHouse.",
  },
  {
    asset: `${DIAGRAMS}/p2-coverage-rounds.png`,
    seconds: 12,
    caption: "Every requirement carries its own success criterion,",
    sub: "so coverage is measured one requirement at a time.",
    light: true,
  },
  {
    asset: `${SHOTS}/43-trace-gap-replan.png`,
    seconds: 12,
    caption: "So it widens the vocabulary for exactly those requirements — period spellings —",
    sub: "searches the same window again, and reaches four of five.",
  },
  {
    asset: `${DIAGRAMS}/p3-specialist-agents.png`,
    seconds: 12,
    caption: "The agent runtime is Google's ADK: planner, researcher and auditor in sequence,",
    sub: "separated by what each can touch. Only the researcher holds the ClickHouse tools.",
    light: true,
  },
  {
    asset: `${SHOTS}/45-trace-sql.png`,
    seconds: 12,
    caption: "Retrieval is read-only SQL through the official ClickHouse MCP server —",
    sub: "parametrized views for the window, vector search, row policies on the tables.",
  },
  {
    asset: `${DIAGRAMS}/01-system-topology.png`,
    seconds: 12,
    caption: "One read path at runtime, one write path for ingestion and migrations,",
    sub: "and 133 migrations behind the schema they share.",
    light: true,
  },
  {
    asset: `${SHOTS}/13-timeline-date-held.png`,
    seconds: 9,
    caption: "The board opens on the record itself: every day of the window,",
    sub: "and how much of the brief the journals corroborate on it.",
  },
  {
    asset: `${SHOTS}/21-requirement-panel.png`,
    seconds: 11,
    caption: "Open a requirement for the verbatim extracts —",
    sub: "and for who wrote what, on which day.",
  },
  {
    asset: `${SHOTS}/24-passage-span.png`,
    seconds: 12,
    caption: "Click a quotation for the stored passage, unedited,",
    sub: "with the exact characters the observation cites: 1,344 to 1,548.",
  },
  {
    asset: `${SHOTS}/31-reference-rights.png`,
    seconds: 8,
    caption: "Every archive reference arrives with its provider,",
    sub: "its catalogue id, and its rights status.",
  },
  {
    asset: `${SHOTS}/50-unmet-requirement.png`,
    seconds: 9,
    caption: "Where these journals are silent, the board says so.",
    sub: "The iron-frame boat is in the history books, not in these three diaries.",
  },
  {
    asset: `${SHOTS}/06-project-odyssey.png`,
    seconds: 7,
    caption: "A second corpus runs the same pipeline.",
    sub: "A poem is read, not dated — so it is addressed by book and line.",
  },
  {
    asset: `${SHOTS}/02-landing-full.png`,
    seconds: 5,
    caption: "SourceCut — scene research from the sources, with the evidence attached.",
    sub: HOSTED_URL,
  },
];

const total = CUT.reduce((sum, shot) => sum + shot.seconds, 0);
console.log(`cut: ${CUT.length} shots, ${total}s (${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")})`);
if (total > 175) throw new Error(`Cut runs ${total}s; the rules cap the video at 180s`);

rmSync(WORK, { recursive: true, force: true });
mkdirSync(WORK, { recursive: true });
mkdirSync(`${ROOT}/output`, { recursive: true });

// ── captions, rendered in the product's own type ────────────────────────────
const CAPTION_CSS = `
  @import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,300;6..72,400&family=Inter:wght@400;500&display=swap');
  html, body { margin: 0; width: ${WIDTH}px; height: ${HEIGHT}px; background: transparent; }
  .bar { position: absolute; left: 0; right: 0; bottom: 0; padding: 46px 96px 54px;
         background: linear-gradient(to top, rgba(8,11,14,0.97) 55%, rgba(8,11,14,0.86) 80%, rgba(8,11,14,0)); }
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
  await page.screenshot({ path: shot.caption_png, omitBackground: true });
}
await browser.close();
console.log("captions rendered");

// ── segments ────────────────────────────────────────────────────────────────
const ffmpeg = (params) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...params]);

CUT.forEach((shot, index) => {
  shot.segment = `${WORK}/segment-${String(index).padStart(2, "0")}.mp4`;
  // A hold, not a push. These frames are dense — a trace, a matrix, a diagram —
  // and a moving frame is a frame nobody finishes reading. Padding rather than
  // cropping for the same reason: the part that carries the point stays in.
  const filter =
    `[0:v]scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,` +
    `pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=${GROUND}[bg];` +
    `[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]`;
  ffmpeg([
    "-loop", "1", "-i", shot.asset,
    "-loop", "1", "-i", shot.caption_png,
    "-filter_complex", filter,
    "-map", "[v]", "-t", String(shot.seconds),
    "-r", String(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
    shot.segment,
  ]);
  console.log(`  segment ${index + 1}/${CUT.length} · ${shot.seconds}s · ${shot.asset.split("/").pop()}`);
});

const list = `${WORK}/segments.txt`;
writeFileSync(list, CUT.map((shot) => `file '${shot.segment}'`).join("\n"), "utf8");
ffmpeg(["-f", "concat", "-safe", "0", "-i", list, "-c", "copy", OUT]);

const probe = execFileSync("ffprobe", [
  "-v", "error", "-show_entries", "format=duration,size", "-of", "default=nw=1", OUT,
]).toString().trim();
console.log(`\n${OUT}\n${probe}`);
