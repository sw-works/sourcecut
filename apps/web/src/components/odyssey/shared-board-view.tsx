"use client";

import { useEffect, useState } from "react";
import styles from "../../styles/odyssey.module.css";

type Shared = { board: { title: string; question: string; summary: string; revision_id: string; sections: { section_id: string; title: string; generated_text: string; user_notes: string; items: { item_id: string; label: string; citation: string; reference_id: string; metadata: Record<string, string> }[] }[] }; provenance_manifest: { manifest_id: string; release_manifest_id: string }; omitted_item_count: number; rights_notice: string; expires_at: string };

export function SharedBoardView({ token }: { token: string }) {
  const [shared, setShared] = useState<Shared | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { fetch(`/sourcecut-api/api/v1/shared/boards/${encodeURIComponent(token)}`).then(async (response) => { if (!response.ok) throw new Error("This frozen share is unavailable or expired."); setShared(await response.json()); }).catch((reason: Error) => setError(reason.message)); }, [token]);
  if (error) return <section className={styles.boardLanding}><p className={styles.eyebrow}>Frozen research board</p><h1>Share unavailable.</h1><p>{error}</p></section>;
  if (!shared) return <p className={styles.loading}>Loading frozen revision…</p>;
  return <article className={styles.sharedBoard}><header><p className={styles.eyebrow}>Read-only research board</p><h1>{shared.board.title}</h1><p>{shared.board.question}</p><small>{shared.rights_notice}</small></header><div>{shared.board.sections.map((section) => <section key={section.section_id}><h2>{section.title}</h2>{section.generated_text && <div className={styles.generatedText}><small>Generated synthesis</small><p>{section.generated_text}</p></div>}{section.user_notes && <blockquote>{section.user_notes}</blockquote>}<ul>{section.items.map((item) => <li key={item.item_id}><strong>{item.label}</strong><span>{item.citation || item.reference_id}</span>{item.metadata.display === "metadata_only" && <em>Image omitted · metadata only</em>}</li>)}</ul></section>)}</div><footer><span>{shared.provenance_manifest.manifest_id}</span><span>{shared.provenance_manifest.release_manifest_id}</span><span>Frozen revision {shared.board.revision_id.slice(0, 8)}</span></footer></article>;
}
