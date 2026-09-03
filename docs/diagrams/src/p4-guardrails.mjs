import { diagram, node } from "./svg.mjs";
// Pattern 4 — defense in depth on model-written SQL (agents/research.py::validate_analytical_query,
// sql/security/odyssey_mcp_role.sql, ADR-013/ADR-014).
export default () => diagram({
  width: 1440, height: 520,
  title: "Pattern 4 · Guardrails — two independent layers on model-written SQL",
  subtitle: "The application refuses queries it cannot vouch for; ClickHouse hides unvalidated rows from the MCP role regardless of what SQL asks for.",
  nodes: [
    node("sql", 40, 190, 190, 70, "model-written SQL", { kind: "llm", sub: "run_query" }),
    node("guard", 290, 176, 260, 96, "validate_analytical_query", {
      kind: "security",
      sub: "one SELECT · allowlisted tables\nLIMIT ≤ 200 · FINAL · date bound",
    }),
    node("refused", 290, 350, 260, 56, "refused to the model", { kind: "blocked", sub: '{"error": reason}' }),
    node("mcp", 620, 190, 200, 70, "mcp-clickhouse", { kind: "ext", sub: "read-only user" }),
    node("policy", 890, 176, 240, 96, "ROW POLICY", {
      kind: "security",
      sub: "trusted = 1 AND\nvalidation_status = 'valid'",
    }),
    node("rows", 1190, 190, 210, 70, "rows the agent may see", { kind: "terminal" }),
  ],
  edges: [
    { from: "sql", to: "guard" },
    { from: "guard", to: "refused", color: "red", label: "never reaches ClickHouse", at: [420, 315] },
    { from: "guard", to: "mcp", label: "approved" },
    { from: "mcp", to: "policy" },
    { from: "policy", to: "rows" },
  ],
  legend: ["llm", "security", "ext", "terminal", "blocked"],
  notes: [
    "The two layers fail differently: the guardrail rejects the query, the policy silently returns fewer rows. Neither depends on prompt adherence.",
    "Every restrictive policy ships with a companion USING 1 TO ALL EXCEPT sourcecut_mcp_role, or ClickHouse would hide the table from ingestion too.",
    "Runtime views filter trusted rows directly as well, so the boundary holds where the console policies were never applied.",
  ],
});
