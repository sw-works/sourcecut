import { diagram, node } from "./svg.mjs";
// Pattern 6 — the only feedback loop in the system (repositories/terms.py, ADR-021).
// Drawn for what it does NOT touch: the evidence tables sit on this page with no edge
// reaching them, which is the whole point of the pattern.
export default () => diagram({
  width: 1300, height: 540,
  title: "Pattern 6 · Memory — the system learns what to look for, never what to believe",
  subtitle: "Search terms a gap round proved productive are written back as curated reference data. No claim, label, or citation is ever derived from them.",
  nodes: [
    node("found", 40, 150, 190, 60, "gap round found\npassages", { kind: "det" }),
    node("remember", 280, 150, 190, 60, "_remember", { kind: "det", sub: "productive categories" }),
    node("repo", 520, 150, 220, 60, "TermExpansionRepository", { kind: "det", sub: "merge, never downgrade" }),
    node("table", 790, 140, 250, 80, "sourcecut.term_expansions", {
      kind: "store",
      sub: "provenance='discovered'\ncurated rows keep theirs",
    }),
    node("later", 520, 320, 260, 60, "a later session's search", { kind: "det", sub: "starts with the wider vocabulary" }),
    node("failed", 260, 320, 210, 56, "memory_write_failed", { kind: "blocked", sub: "board still returns" }),
    node("evidence", 880, 320, 250, 70, "sourcecut.observations", { kind: "store", sub: "no edge reaches this box" }),
  ],
  edges: [
    { from: "found", to: "remember" },
    { from: "remember", to: "repo" },
    { from: "repo", to: "table" },
    {
      from: "repo", to: "failed", color: "red",
      points: [[560, 212], [560, 258], [365, 258], [365, 318]],
      label: "write fails", at: [462, 258],
    },
    {
      from: "table", to: "later", muted: true,
      points: [[915, 222], [915, 272], [650, 272], [650, 318]],
      label: "next plan's terms", at: [782, 272],
    },
  ],
  legend: ["det", "store", "blocked"],
  notes: [
    "Confined to curated reference data (ADR-017): it changes what SourceCut looks for, never what SourceCut believes.",
    "Vocabulary memory is an optimization, so a failed write is an event, not a lost board.",
    "No curation surface yet — discovered rows are reversible by provenance, but only by hand (deferred.md).",
  ],
});
