"use client";

import { FormEvent, useState } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

type Record = { record_id: string; revision: number; target_type: string; target_id: string; proposed_changes: globalThis.Record<string, unknown>; rationale: string; citations: string[]; status: string; proposer_id: string; reviewer_id: string; review_note: string; updated_at: string };
type Coverage = { by_target: globalThis.Record<string, number>; by_status: globalThis.Record<string, number>; trusted_percent: number; license_records_trusted: number; unresolved_records: number; import_runs: number; active_release_id: string };

const API = "/sourcecut-api/api/v1/admin/odyssey";

export function CurationConsole() {
  const [key, setKey] = useState("");
  const [records, setRecords] = useState<Record[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [message, setMessage] = useState("Enter the configured admin credential to load the queue.");
  const [targetType, setTargetType] = useState("entity");
  const [targetId, setTargetId] = useState("polyphemus");
  const [label, setLabel] = useState("Polyphemus");

  const headers = { "Content-Type": "application/json", "X-SourceCut-Admin-Key": key };

  async function refresh() {
    const [queueResponse, coverageResponse] = await Promise.all([fetch(`${API}/reviews`, { headers }), fetch(`${API}/coverage`, { headers })]);
    if (!queueResponse.ok || !coverageResponse.ok) { setMessage("Authentication failed or curation is unavailable."); return; }
    setRecords(await queueResponse.json()); setCoverage(await coverageResponse.json()); setMessage("Queue and coverage refreshed.");
  }

  async function propose(event: FormEvent) {
    event.preventDefault();
    const response = await fetch(`${API}/proposals`, { method: "POST", headers, body: JSON.stringify({ target_type: targetType, target_id: targetId, base_revision_id: "current-trusted-release", proposed_changes: { canonical_label: label }, rationale: "Curator correction submitted through the review console.", citations: ["Od. 9.187–542"], proposer_id: "console-curator" }) });
    setMessage(response.ok ? "Draft proposal created; it does not alter the trusted layer." : "Proposal failed validation."); if (response.ok) await refresh();
  }

  async function decide(record: Record, status: "reviewed" | "trusted" | "rejected") {
    const response = await fetch(`${API}/proposals/${record.record_id}/decisions`, { method: "POST", headers, body: JSON.stringify({ expected_revision: record.revision, status, reviewer_id: "console-reviewer", review_note: `Reviewed in the curation console and marked ${status}.` }) });
    setMessage(response.ok ? `Revision ${record.revision + 1} recorded as ${status}.` : "Decision failed; refresh if another reviewer changed this record."); await refresh();
  }

  return <div className={styles.curationConsole}><header><p className={styles.eyebrow}>SourceCut operations</p><h1>Odyssey curation.</h1><p>Review derived annotations, validate licenses, compare releases, and preserve every decision. Raw source records cannot be edited here.</p><div><input type="password" value={key} onChange={(event) => setKey(event.target.value)} placeholder="Admin credential" aria-label="Admin credential" /><button onClick={refresh}>Load review queue</button></div><small aria-live="polite">{message}</small></header>
    {coverage && <section className={styles.coverageStrip}><article><strong>{coverage.trusted_percent}%</strong><span>Trusted</span></article><article><strong>{coverage.unresolved_records}</strong><span>Unresolved</span></article><article><strong>{coverage.license_records_trusted}</strong><span>Licenses cleared</span></article><article><strong>{coverage.import_runs}</strong><span>Import manifests</span></article><p>Active release<br/><b>{coverage.active_release_id || "No promoted release"}</b></p></section>}
    <section className={styles.curationComposer}><div><p className={styles.eyebrow}>New proposal</p><h2>Correct a derived record.</h2><p>Proposals enter draft state and require separate reviewed and trusted decisions.</p></div><form onSubmit={propose}><label>Record type<select value={targetType} onChange={(event) => setTargetType(event.target.value)}>{["entity", "event", "speech", "morphology", "alignment", "claim", "place_hypothesis", "license"].map((value) => <option key={value}>{value}</option>)}</select></label><label>Target ID<input value={targetId} onChange={(event) => setTargetId(event.target.value)} /></label><label>Proposed label<input value={label} onChange={(event) => setLabel(event.target.value)} /></label><button>Create draft</button></form></section>
    <section className={styles.reviewQueue}><header><p className={styles.eyebrow}>Review queue</p><h2>{records.length} versioned proposals</h2></header>{records.length === 0 && <p>No records loaded.</p>}{records.map((record) => <article key={record.record_id}><div><span>{record.target_type} · revision {record.revision}</span><h3>{record.target_id}</h3><p>{record.rationale}</p><small>{record.citations.join(" · ")}</small></div><pre>{JSON.stringify(record.proposed_changes, null, 2)}</pre><aside><strong>{record.status}</strong>{record.status === "draft" && <><button onClick={() => decide(record, "reviewed")}>Mark reviewed</button><button onClick={() => decide(record, "rejected")}>Reject</button></>}{record.status === "reviewed" && <><button onClick={() => decide(record, "trusted")}>Promote trusted</button><button onClick={() => decide(record, "rejected")}>Reject</button></>}</aside></article>)}</section>
  </div>;
}
