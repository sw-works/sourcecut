import { diagram, node } from "./svg.mjs";
// Pattern 2 — goal setting and monitoring (services/board.py::_close_coverage_gaps, ADR-020).
// Each requirement carries its own success criterion, so "did we find enough" is a
// computed answer per requirement rather than a judgement about the board as a whole.
export default () => diagram({
  width: 1420, height: 540,
  title: "Pattern 2 · Goal monitoring — coverage decides whether to research again",
  subtitle: "Every planned requirement is scored against its own criterion. Unmet ones get exactly one widened round, and what stays unmet is reported.",
  nodes: [
    node("evidence", 40, 160, 190, 60, "retrieved evidence", { kind: "store", sub: "plan window" }),
    node("score", 290, 160, 220, 60, "evaluate_coverage", { kind: "det", sub: "per requirement" }),
    node("met", 580, 116, 220, 48, "met", { kind: "terminal" }),
    node("gaps", 580, 215, 220, 48, "unmet · single_source", { kind: "state" }),
    node("expand", 860, 205, 210, 56, "expand_gaps", { kind: "llm", sub: "period spellings only" }),
    node("search", 860, 320, 210, 56, "gap_passage_query", { kind: "det", sub: "same window, wider terms" }),
    node("unmet", 1150, 320, 220, 56, "reported unmet", { kind: "blocked", sub: "shown, not hidden" }),
  ],
  edges: [
    { from: "evidence", to: "score" },
    { from: "score", to: "met", label: "≥ minimum_authors", at: [400, 128] },
    { from: "score", to: "gaps" },
    { from: "gaps", to: "expand", label: "only these", at: [820, 296] },
    { from: "expand", to: "search", label: "widened vocabulary", at: [1000, 296] },
    { from: "search", to: "unmet", color: "red", label: "nothing found", at: [1110, 402] },
    {
      from: "search", to: "score",
      label: "round 2 · bounded by SOURCECUT_RESEARCH_ROUNDS",
      points: [[860, 348], [820, 348], [820, 430], [400, 430], [400, 222]], at: [610, 430],
    },
  ],
  legend: ["det", "llm", "store", "state", "terminal", "blocked"],
  notes: [
    "A round widens vocabulary only. It never widens the window, never lowers a criterion, and never runs a third time.",
    "Gap evidence keeps passage-term: citation ids, so it stays distinguishable from validated observations.",
  ],
});
