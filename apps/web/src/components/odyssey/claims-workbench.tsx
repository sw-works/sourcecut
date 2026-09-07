"use client";

import { useEffect, useState } from "react";
import type { SubmitEvent } from "react";
import styles from "../../styles/odyssey.module.css";

const API = "/sourcecut-api/api/v1";
type Evidence = { claim_evidence_id: string; support_role: string; source_kind: string; source_record_id: string; version_id: string | null; source_quote: string; citation: string; validation_status: string; validation_errors: string[]; trusted: boolean; source_unit_hash: string | null };
type Matrix = { claim_id: string; claim_text: string; evidence_class: string; confidence: string; review_status: string; translation_dependent: boolean; supports: Evidence[]; qualifies: Evidence[]; conflicts: Evidence[]; context: Evidence[]; limitations: string[]; publication_ready: boolean };
type DraftEvidence = { support_role: string; source_kind: string; source_record_id: string; version_id: string; source_quote: string; source_start: number; source_end: number; citation: string };
type Trace = { claim: { claim_id: string; model_id: string; prompt_hash: string | null; schema_version: string; validator_version: string; reviewer_id: string; review_note: string }; evidence_chain: { claim_evidence_id: string; evidence: Evidence; source: Record<string, unknown> | null }[] };

export default function ClaimsWorkbench() {
  const [matrix, setMatrix] = useState<Matrix[]>([]);
  const [claimText, setClaimText] = useState("");
  const [category, setCategory] = useState("language");
  const [evidenceClass, setEvidenceClass] = useState("PRIMARY_GREEK_EXPLICIT");
  const [confidence, setConfidence] = useState("HIGH");
  const [evidence, setEvidence] = useState<DraftEvidence[]>([]);
  const [unsupportedQuestion, setUnsupportedQuestion] = useState("");
  const [trace, setTrace] = useState<Trace | null>(null);
  const [decision, setDecision] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    refresh();
    const raw = window.sessionStorage.getItem("odyssey-claim-draft");
    if (raw) {
      const draft = JSON.parse(raw) as { evidence: DraftEvidence[]; suggested_claim?: string };
      setEvidence(draft.evidence); setClaimText(draft.suggested_claim ?? "");
      if (draft.evidence.some((item) => !item.version_id.endsWith("grc2"))) setEvidenceClass("TRANSLATION_WORDING");
      window.sessionStorage.removeItem("odyssey-claim-draft");
    }
  }, []);

  async function refresh() {
    const response = await fetch(`${API}/claims/matrix`);
    if (response.ok) setMatrix(await response.json());
  }

  async function createClaim(event: SubmitEvent) {
    event.preventDefault(); setBusy(true); setError("");
    const unsupported = evidenceClass === "UNSUPPORTED";
    const response = await fetch(`${API}/claims`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ claim_text: claimText, claim_category: category, evidence_class: evidenceClass, confidence, unsupported_question: unsupported ? unsupportedQuestion : "", evidence: unsupported ? [] : evidence }) });
    if (!response.ok) { const body = await response.json(); setError(typeof body.detail === "string" ? body.detail : "The claim contract was rejected."); setBusy(false); return; }
    setClaimText(""); setEvidence([]); setUnsupportedQuestion(""); setBusy(false); await refresh();
  }

  async function loadTrace(claimId: string) {
    setDecision([]);
    const response = await fetch(`${API}/claims/${encodeURIComponent(claimId)}/trace`);
    if (response.ok) setTrace(await response.json());
  }

  async function checkPublication(claimId: string) {
    const response = await fetch(`${API}/claims/${encodeURIComponent(claimId)}/publication`, { method: "POST" });
    const body = await response.json();
    setDecision(response.ok ? ["Publication boundary passed."] : body.detail.reasons);
    if (!trace || trace.claim.claim_id !== claimId) await loadTrace(claimId);
  }

  const unsupported = evidenceClass === "UNSUPPORTED";
  return <div className={styles.claimsWorkbench}>
    <header className={styles.claimsHero}><p className={styles.eyebrow}>Claims are not passages</p><h1>Make the inference<br />show its work.</h1><p>Evidence class, confidence, and review status remain independent. Exact spans validate against immutable source units before a claim can approach publication.</p></header>
    <section className={styles.claimComposer} aria-labelledby="claim-composer-title"><div><p className={styles.eyebrow}>New claim</p><h2 id="claim-composer-title">Compose from evidence</h2><p>{evidence.length > 0 ? `${evidence.length} exact source unit${evidence.length === 1 ? "" : "s"} arrived from the reader.` : "Select lines in the reader, or record an unsupported question explicitly."}</p>{evidence.length === 0 && <a href="/odyssey/read/1">Select text in the reader →</a>}</div>
      <form onSubmit={createClaim}><label>Claim<textarea value={claimText} onChange={(event) => setClaimText(event.target.value)} required minLength={5} placeholder="State one bounded claim…" /></label><div className={styles.claimFields}><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}>{["language", "translation", "narrative", "character", "setting", "geography", "material culture", "reception"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Evidence class<select value={evidenceClass} onChange={(event) => { const next = event.target.value; setEvidenceClass(next); if (next === "UNSUPPORTED") setConfidence("UNKNOWN"); }}>{["PRIMARY_GREEK_EXPLICIT", "TRANSLATION_WORDING", "TEXTUAL_INFERENCE", "VARIANT_READING", "MODERN_SCHOLARLY_INTERPRETATION", "CONTEXT_ONLY", "UNSUPPORTED"].map((item) => <option key={item}>{item}</option>)}</select></label><label>Confidence<select value={confidence} onChange={(event) => setConfidence(event.target.value)} disabled={unsupported}>{["HIGH", "MEDIUM", "LOW", "CONFLICTED", "UNKNOWN"].map((item) => <option key={item}>{item}</option>)}</select></label></div>
        {unsupported ? <label>Unanswered question<input value={unsupportedQuestion} onChange={(event) => setUnsupportedQuestion(event.target.value)} required placeholder="What cannot the current evidence establish?" /></label> : <div className={styles.draftEvidence}>{evidence.map((item) => <article key={item.source_record_id}><span>{item.support_role}</span><blockquote>{item.source_quote}</blockquote><small>{item.citation} · {item.version_id}</small></article>)}{evidence.length === 0 && <p>No exact evidence attached. The API will reject a supported claim.</p>}</div>}
        {error && <p className={styles.readerError} role="alert">{error}</p>}<button disabled={busy}>{busy ? "Validating exact spans…" : unsupported ? "Record unsupported question" : "Validate and add claim"}</button></form>
    </section>
    <section className={styles.evidenceMatrix} aria-labelledby="evidence-matrix-title"><header><div><p className={styles.eyebrow}>Evidence matrix</p><h2 id="evidence-matrix-title">Claims under review</h2></div><p>{matrix.length} claims · {matrix.filter((item) => item.publication_ready).length} publication-ready</p></header>
      {matrix.length === 0 ? <div className={styles.matrixEmpty}><h3>No claims yet.</h3><p>The empty matrix is honest: passages become evidence only when someone states and validates a bounded claim.</p></div> : <div className={styles.claimRows}>{matrix.map((claim, index) => <article key={claim.claim_id} className={claim.evidence_class === "UNSUPPORTED" ? styles.unsupportedClaim : ""}><div className={styles.claimNumber}>{String(index + 1).padStart(2, "0")}</div><div className={styles.claimStatement}><span>{claim.evidence_class}</span><h3>{claim.claim_text}</h3><div className={styles.claimStatus}><b>{claim.confidence}</b><b>{claim.review_status}</b>{claim.translation_dependent && <b>translation-dependent</b>}{claim.publication_ready && <b>publication-ready</b>}</div>{claim.limitations.map((item) => <p key={item}>{item}</p>)}<div><button onClick={() => loadTrace(claim.claim_id)}>Trace provenance</button><button onClick={() => checkPublication(claim.claim_id)}>Check publication</button></div></div><EvidenceRoles claim={claim} /></article>)}</div>}
    </section>
    {trace && <aside className={styles.traceDrawer} aria-label="Claim provenance trace"><button aria-label="Close provenance trace" onClick={() => { setTrace(null); setDecision([]); }}>×</button><p className={styles.eyebrow}>Claim → evidence → source</p><h2>Provenance trace</h2>{decision.length > 0 && <div className={styles.publicationDecision}>{decision.map((item) => <p key={item}>{item}</p>)}</div>}<dl><div><dt>Claim ID</dt><dd>{trace.claim.claim_id}</dd></div><div><dt>Schema</dt><dd>{trace.claim.schema_version}</dd></div><div><dt>Validator</dt><dd>{trace.claim.validator_version}</dd></div><div><dt>Model</dt><dd>{trace.claim.model_id || "human-created"}</dd></div><div><dt>Prompt hash</dt><dd>{trace.claim.prompt_hash || "not applicable"}</dd></div><div><dt>Reviewer</dt><dd>{trace.claim.reviewer_id || "not reviewed"}</dd></div></dl>{trace.evidence_chain.map((item) => <article key={item.claim_evidence_id}><span className={item.evidence.validation_status === "valid" ? styles.validEvidence : styles.invalidEvidence}>{item.evidence.validation_status}</span><h3>{item.evidence.citation || item.evidence.source_record_id}</h3><blockquote>{item.evidence.source_quote || "Curated reference record"}</blockquote><p>{item.evidence.support_role} · {item.evidence.source_kind}</p>{item.evidence.validation_errors.map((error) => <p className={styles.traceError} key={error}>{error}</p>)}{item.source && <><a href={(item.source.source_url as string) || "#"}>Open pinned source</a><small>{(item.source.bibliographic_description as string) || (item.source.citation_text as string)}</small></>}</article>)}</aside>}
  </div>;
}

function EvidenceRoles({ claim }: { claim: Matrix }) {
  const groups: [string, Evidence[]][] = [["Supports", claim.supports], ["Qualifies", claim.qualifies], ["Conflicts", claim.conflicts], ["Context", claim.context]];
  return <div className={styles.evidenceRoles}>{groups.map(([label, items]) => <section key={label}><h4>{label}<span>{items.length}</span></h4>{items.map((item) => <div key={item.claim_evidence_id}><span className={item.validation_status === "valid" ? styles.validEvidence : styles.invalidEvidence}>{item.validation_status}</span><p>{item.source_quote || item.citation || item.source_record_id}</p><small>{item.version_id || item.source_kind}</small></div>)}</section>)}</div>;
}
