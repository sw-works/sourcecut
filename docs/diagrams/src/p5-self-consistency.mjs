import { diagram, node } from "./svg.mjs";
// Pattern 5 — self-consistency over one passage (pipelines/extraction/consistency.py).
// Candidates are matched on the span they claim, so two runs agree only when they point
// at the same words for the same reason.
export default () => diagram({
  width: 1240, height: 540,
  title: "Pattern 5 · Self-consistency — disagreement becomes a filter",
  subtitle: "One passage, three independent samples in parallel. A candidate only survives if it recurs on the same span.",
  nodes: [
    node("passage", 40, 215, 190, 60, "one passage", { kind: "store", sub: "temperature 0" }),
    node("r1", 300, 120, 190, 46, "extract", { kind: "llm" }),
    node("r2", 300, 190, 190, 46, "extract", { kind: "llm" }),
    node("r3", 300, 260, 190, 46, "extract", { kind: "llm" }),
    node("vote", 560, 190, 210, 70, "consensus_key", {
      kind: "det",
      sub: "(category, term,\nsource_start, source_end)",
    }),
    node("kept", 840, 150, 230, 50, "kept · seen ≥ 2 of 3", { kind: "terminal" }),
    node("dropped", 840, 250, 230, 50, "discarded · seen once", { kind: "blocked" }),
    node("result", 840, 360, 230, 60, "ExtractionResult", { kind: "store", sub: "prompt_version +sc3of2" }),
  ],
  edges: [
    { from: "passage", to: "r1", points: [[232, 245], [265, 245], [265, 143], [298, 143]] },
    { from: "passage", to: "r2", points: [[232, 245], [265, 245], [265, 213], [298, 213]] },
    { from: "passage", to: "r3", points: [[232, 245], [265, 245], [265, 283], [298, 283]] },
    { from: "r1", to: "vote", points: [[490, 143], [525, 143], [525, 225], [558, 225]] },
    { from: "r2", to: "vote", points: [[490, 213], [525, 213], [525, 225], [558, 225]] },
    { from: "r3", to: "vote", points: [[490, 283], [525, 283], [525, 225], [558, 225]] },
    { from: "vote", to: "kept", label: "one vote per run", at: [722, 152] },
    { from: "vote", to: "dropped", color: "red" },
    {
      from: "kept", to: "result",
      points: [[1072, 175], [1130, 175], [1130, 390], [1074, 390]],
      label: "fresh\nidempotency key", at: [1150, 285],
    },
  ],
  legend: ["llm", "det", "store", "terminal", "blocked"],
  notes: [
    "Runs go out in parallel, so the wall-clock cost is one extraction rather than three.",
    "This narrows what reaches span validation; it does not replace it.",
    "Not yet wired into corpus ingestion — the precision gain is unmeasured (deferred.md).",
  ],
});
