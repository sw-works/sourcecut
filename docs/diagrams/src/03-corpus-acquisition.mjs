import { diagram, node } from "./svg.mjs";
// 03 — corpus acquisition (Task 028, ADR-023/024/025). Specified, not built.
// The whole point of the drawing is the vertical line: the open web is on the
// ingestion side of it and can never cross to the runtime side.
export default () => diagram({
  width: 1660, height: 700,
  title: "03 · Corpus acquisition",
  subtitle: "Acquisition searches the open web; runtime never does. A source arrives trusted only after a human admits its repository and promotes its release.",
  groups: [
    { x: 24, y: 84, w: 1180, h: 500, label: "ingestion — may reach the open web" },
    { x: 1228, y: 84, w: 408, h: 500, label: "runtime — closed" },
  ],
  nodes: [
    node("repos", 48, 122, 226, 62, "admitted repositories", { kind: "human", sub: "licenses.reviewed_by", badge: "human" }),
    node("discover", 48, 232, 226, 66, "discovery", { kind: "llm", sub: "2–5 acquisition\nperspectives" }),
    node("web", 48, 348, 226, 56, "public-domain repositories", { kind: "ext", sub: "Gutenberg · IA · LoC · HathiTrust" }),
    node("candidates", 320, 232, 214, 66, "candidate_sources", { kind: "store", sub: "rights field, verbatim" }),

    node("rights", 578, 226, 214, 78, "rights determination", { kind: "security", sub: "the repository's declared\nfield, and nothing else" }),
    node("ineligible", 578, 356, 214, 56, "ineligible", { kind: "blocked", sub: "recorded with the reason" }),

    node("fetch", 836, 122, 214, 62, "fetch + register", { kind: "det", sub: "raw_sha256 · revision" }),
    node("segment", 836, 216, 214, 62, "segment + extract", { kind: "det", sub: "spans · hashes · versions" }),
    node("staged", 836, 310, 214, 62, "staged release", { kind: "store", sub: "not trusted · invisible to MCP" }),
    node("fidelity", 836, 404, 214, 70, "fidelity report", { kind: "det", sub: "OCR · drift · span failures" }),
    node("promote", 836, 500, 214, 62, "promotion", { kind: "human", sub: "actor + reason recorded", badge: "human" }),

    node("corpus", 1252, 226, 360, 78, "the loaded corpus", { kind: "terminal", sub: "trusted observations,\nindistinguishable by origin" }),
    node("agent", 1252, 404, 360, 70, "research agent", { kind: "llm", sub: "reads ClickHouse through MCP" }),
  ],
  edges: [
    { from: "repos", to: "discover", label: "only these", at: [232, 208] },
    { from: "discover", to: "web", label: "search", at: [200, 326] },
    { from: "discover", to: "candidates" },
    { from: "web", to: "candidates", muted: true, points: [[276, 372], [298, 372], [298, 288], [318, 288]] },
    { from: "candidates", to: "rights" },
    { from: "rights", to: "ineligible", color: "red", label: "missing · hedged · unrecognised", at: [468, 340] },
    { from: "rights", to: "fetch", label: "eligible", points: [[794, 250], [816, 250], [816, 153], [834, 153]], at: [816, 118] },
    { from: "fetch", to: "segment" },
    { from: "segment", to: "staged" },
    { from: "staged", to: "fidelity" },
    { from: "fidelity", to: "promote" },
    {
      from: "fidelity", to: "staged", color: "red", muted: false,
      points: [[1052, 438], [1104, 438], [1104, 340], [1052, 340]],
      label: "below baseline:\nnot promoted", at: [1132, 390],
    },
    {
      from: "promote", to: "corpus",
      points: [[1052, 530], [1160, 530], [1160, 265], [1250, 265]],
      label: "now eligible for trusted", at: [1208, 530],
    },
    { from: "corpus", to: "agent", label: "run_query", at: [1330, 350] },
  ],
  legend: ["det", "llm", "human", "security", "store", "ext", "terminal", "blocked"],
  notes: [
    "Specified in tasks/028-corpus-acquisition.md; not built. The runtime column is what exists today.",
    "The model proposes what to look for and never decides rights: eligibility reads one declared field on an already-reviewed repository.",
    "Two human gates, both coarse: a repository is admitted once, a release is promoted once. Neither scales with document count.",
  ],
});
