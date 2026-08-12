"use client";

import { useState } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

type BoardItem = {
  item_id: string;
  kind: string;
  reference_id: string;
  label: string;
  citation: string;
  rights_status: string;
  metadata: Record<string, unknown>;
};
type Section = {
  section_id: string;
  title: string;
  generated_text: string;
  user_notes: string;
  items: BoardItem[];
  warnings: string[];
  conflicts: string[];
  unresolved_questions: string[];
  hidden_generated_text: boolean;
};
type Board = {
  board_id: string;
  revision_id: string;
  title: string;
  question: string;
  summary: string;
  sections: Section[];
  release_pins: {
    release_manifest_id: string;
    corpus_revision: string;
    annotation_release_ids: string[];
    active_versions: string[];
    active_hypotheses: string[];
  };
  warnings: string[];
  conflicts: string[];
  unsupported_questions: string[];
  agent_trace: unknown[];
  source_session_id: string;
  created_at: string;
  updated_at: string;
};

const API = "/sourcecut-api";
const pins = {
  release_manifest_id: "odyssey-perseus-790c84289edb",
  corpus_revision: "790c84289edbdbe289dd7b752bfea29f0af4299d",
  annotation_release_ids: ["odyssey-treebank-2.1"],
  active_versions: ["odyssey-perseus-grc2", "odyssey-perseus-eng3", "odyssey-perseus-eng4"],
  active_hypotheses: ["textual-sequence"],
};
const initialSections: Section[] = [
  section("narrative-context", "Narrative Context", [item("event", "odyssey-event-009-01", "The Cyclopeia begins", "Od. 9.105")]),
  section("setting", "Setting", [item("map_view", "textual-sequence", "Textual voyage sequence", "Od. 9.39–566")]),
  section("characters", "Characters", [item("entity", "polyphemus", "Polyphemus", "Od. 9.187–542")]),
  section("actions-and-blocking", "Actions and Blocking"),
  section("objects-and-material-culture", "Objects and Material Culture", [item("asset", "met-251485", "Probable Odysseus oinochoe", "The Met 25.148.5", "PUBLIC_DOMAIN")]),
  section("language-and-translation", "Language and Translation", [item("passage", "urn:cts:greekLit:tlg0012.tlg002.perseus-grc2:9.105-115", "Cyclopes introduced", "Od. 9.105–115")]),
  section("geography", "Geography"),
  section("visual-reception", "Visual Reception"),
  section("conflicts-and-unknowns", "Conflicts and Unknowns"),
  section("source-list", "Source List"),
];

function item(kind: string, reference_id: string, label: string, citation: string, rights_status = ""): BoardItem {
  return { item_id: `${kind}:${reference_id}`, kind, reference_id, label, citation, rights_status, metadata: {} };
}
function section(section_id: string, title: string, items: BoardItem[] = []): Section {
  return { section_id, title, generated_text: "", user_notes: "", items, warnings: [], conflicts: [], unresolved_questions: [], hidden_generated_text: false };
}

export function BoardWorkspace() {
  const [board, setBoard] = useState<Board | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Create a pinned workspace to begin.");
  const [exportFormat, setExportFormat] = useState("pdf");

  async function createBoard() {
    setBusy(true);
    const response = await fetch(`${API}/api/v1/boards`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: "Odysseus and Polyphemus — Book 9", question: "How does the poem construct Odysseus’s encounter with Polyphemus?", summary: "A manually assembled, citation-first workspace.", sections: initialSections, release_pins: pins, warnings: ["Geographic identifications remain hypothesis-dependent."], unsupported_questions: ["The poem does not establish a uniquely mappable modern cave."] }) });
    if (!response.ok) { setMessage("The workspace could not be created."); setBusy(false); return; }
    setBoard(await response.json()); setMessage("Workspace created and pinned."); setBusy(false);
  }

  function updateNotes(sectionId: string, value: string) {
    if (!board) return;
    setBoard({ ...board, sections: board.sections.map((entry) => entry.section_id === sectionId ? { ...entry, user_notes: value } : entry) });
  }

  function moveSection(index: number, direction: -1 | 1) {
    if (!board) return;
    const target = index + direction;
    if (target < 0 || target >= board.sections.length) return;
    const sections = [...board.sections];
    [sections[index], sections[target]] = [sections[target], sections[index]];
    setBoard({ ...board, sections });
  }

  async function saveBoard() {
    if (!board) return;
    setBusy(true);
    const response = await fetch(`${API}/api/v1/boards/${board.board_id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision_id: board.revision_id, sections: board.sections }) });
    if (response.status === 409) { setMessage("This board changed elsewhere. Reload before saving."); setBusy(false); return; }
    if (!response.ok) { setMessage("Save failed; your local notes remain visible."); setBusy(false); return; }
    setBoard(await response.json()); setMessage("New immutable revision saved."); setBusy(false);
  }

  async function snapshot() {
    if (!board) return;
    setBusy(true);
    const response = await fetch(`${API}/api/v1/boards/${board.board_id}/snapshot`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision_id: board.revision_id }) });
    setMessage(response.ok ? "Frozen snapshot created." : "Snapshot could not be created."); setBusy(false);
  }

  async function duplicate() {
    if (!board) return;
    setBusy(true);
    const response = await fetch(`${API}/api/v1/boards/${board.board_id}/duplicate`, { method: "POST" });
    if (response.ok) { setBoard(await response.json()); setMessage("Independent duplicate created."); } else setMessage("Duplicate could not be created.");
    setBusy(false);
  }

  async function exportBoard() {
    if (!board) return;
    setBusy(true);
    const response = await fetch(`${API}/api/v1/boards/${board.board_id}/exports`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision_id: board.revision_id, format: exportFormat, display_policy: "public_reusable" }) });
    if (response.ok) { const job = await response.json(); window.location.assign(`${API}${job.download_url}`); setMessage(`Prepared ${exportFormat.replace("_", " ")} with a provenance manifest.`); } else setMessage("Export could not be prepared.");
    setBusy(false);
  }

  async function shareBoard() {
    if (!board) return;
    setBusy(true);
    const response = await fetch(`${API}/api/v1/boards/${board.board_id}/shares`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ revision_id: board.revision_id, expires_in_days: 30 }) });
    if (response.ok) { const link = await response.json(); window.open(`/odyssey/shared/${encodeURIComponent(link.share_token)}`, "_blank", "noopener,noreferrer"); setMessage("Opened a frozen, rights-filtered share page."); } else setMessage("Share link could not be created.");
    setBusy(false);
  }

  if (!board) return <section className={styles.boardLanding}><p className={styles.eyebrow}>Research workspace</p><h1>Build an argument without losing its evidence.</h1><p>Save passages, claims, routes, entities, events, and objects as stable references. Generated synthesis and your notes remain separate.</p><button onClick={createBoard} disabled={busy}>{busy ? "Creating…" : "Create Book 9 board"}</button><small aria-live="polite">{message}</small></section>;

  return <div className={styles.boardWorkspace}>
    <header className={styles.boardHeader}><div><p className={styles.eyebrow}>Pinned research board</p><h1>{board.title}</h1><p>{board.question}</p></div><div className={styles.boardActions}><button onClick={saveBoard} disabled={busy}>Save revision</button><button onClick={snapshot} disabled={busy}>Freeze snapshot</button><button onClick={duplicate} disabled={busy}>Duplicate</button><select aria-label="Export format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value)}><option value="pdf">PDF</option><option value="html">HTML</option><option value="markdown">Markdown</option><option value="json">Canonical JSON</option><option value="citations_text">Citations · text</option><option value="citations_markdown">Citations · Markdown</option><option value="csl_json">CSL-JSON</option><option value="bibtex">BibTeX</option><option value="geojson">GeoJSON</option><option value="map_png">Map PNG</option></select><button onClick={exportBoard} disabled={busy}>Export</button><button onClick={shareBoard} disabled={busy}>Share frozen</button></div></header>
    <aside className={styles.boardManifest}><strong>{board.release_pins.release_manifest_id}</strong><span>Corpus {board.release_pins.corpus_revision.slice(0, 12)}</span><span>{board.release_pins.active_versions.length} text versions</span><span>{board.agent_trace.length} trace events</span></aside>
    {(board.warnings.length > 0 || board.unsupported_questions.length > 0) && <section className={styles.boardWarnings}><h2>Limits remain visible</h2>{board.warnings.map((warning) => <p key={warning}>Warning — {warning}</p>)}{board.unsupported_questions.map((question) => <p key={question}>Unresolved — {question}</p>)}</section>}
    <div className={styles.boardColumns}>{board.sections.map((entry, index) => <article className={styles.boardCard} key={entry.section_id}><header><span>{String(index + 1).padStart(2, "0")}</span><h2>{entry.title}</h2><div><button aria-label={`Move ${entry.title} up`} onClick={() => moveSection(index, -1)}>↑</button><button aria-label={`Move ${entry.title} down`} onClick={() => moveSection(index, 1)}>↓</button></div></header>{entry.generated_text && <div className={styles.generatedText}><small>Generated synthesis · preserved</small><p>{entry.generated_text}</p></div>}<ul>{entry.items.map((saved) => <li key={saved.item_id}><span>{saved.kind.replace("_", " ")}</span><strong>{saved.label}</strong><small>{saved.citation}</small>{saved.rights_status && <em>{saved.rights_status.replace("_", " ")}</em>}</li>)}</ul><label>Your notes<textarea value={entry.user_notes} onChange={(event) => updateNotes(entry.section_id, event.target.value)} placeholder="Add interpretation, questions, or teaching notes…" /></label></article>)}</div>
    <footer className={styles.boardStatus} aria-live="polite"><span>Revision {board.revision_id.slice(0, 8)}</span><p>{message}</p></footer>
  </div>;
}
