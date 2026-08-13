"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";

const API = "/sourcecut-api";
const STORED_JOB_KEY = "sourcecut.previs.job";

export type PrevisAsset = {
  asset: {
    asset_id: string;
    title: string;
    thumbnail_path: string;
    rights_status: string;
  };
};

export type PrevisSection = { title: string; assets: PrevisAsset[] };

type SupportedDetail = {
  detail: string;
  observation_ids: string[];
  passage_ids: string[];
};

type BriefEnvelope = {
  brief: {
    shot_brief_id: string;
    shot_type: string;
    strictness: string;
    duration_seconds: number;
    aspect_ratio: string;
    reference_asset_ids: string[];
    producer_model: string;
    content: {
      purpose: string;
      setting: string;
      action: string;
      composition: string;
      camera_motion: string;
      ambience: string;
      supported_details: SupportedDetail[];
      interpretive_additions: string[];
      excluded_details: string[];
    };
  };
  brief_fingerprint: string;
  estimated_cost_usd: number | null;
  can_generate: boolean;
  blockers: string[];
};

type Finding = {
  label: "supported" | "interpretive" | "unsupported";
  visible_detail: string;
  approximate_time_range: string;
  severity: string;
  rationale: string;
};

type JobEnvelope = {
  job: {
    job_id: string;
    status: "queued" | "generating" | "reviewing" | "complete" | "failed" | "blocked";
    model: string;
    estimated_cost_usd: number;
    generation_count: number;
    safe_error: string;
  };
  job_fingerprint: string;
  report: {
    overall_result: string;
    findings: Finding[];
    correction_instructions: string[];
  } | null;
  disclosure: string;
  video_url: string;
};

type Props = {
  open: boolean;
  sessionId: string;
  section: PrevisSection | null;
  onClose: () => void;
  onRecover: () => void;
};

export default function PrevisPanel({ open, sessionId, section, onClose, onRecover }: Props) {
  const [shotType, setShotType] = useState("establishing_shot");
  const [strictness, setStrictness] = useState("strict");
  const [duration, setDuration] = useState(8);
  const [aspectRatio, setAspectRatio] = useState("16:9");
  const [references, setReferences] = useState<string[]>([]);
  const [brief, setBrief] = useState<BriefEnvelope | null>(null);
  const [job, setJob] = useState<JobEnvelope | null>(null);
  const [paidApproved, setPaidApproved] = useState(false);
  const [correctionApproved, setCorrectionApproved] = useState(false);
  const [activity, setActivity] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!section) return;
    const firstReference = section.assets.find(
      (item) => item.asset.rights_status === "public_domain" && item.asset.thumbnail_path,
    );
    setReferences(firstReference ? [firstReference.asset.asset_id] : []);
    setBrief(null);
    setJob(null);
    setPaidApproved(false);
    setCorrectionApproved(false);
    setError("");
  }, [section]);

  useEffect(() => {
    const jobId = window.localStorage.getItem(STORED_JOB_KEY);
    if (!jobId) return;
    void apiJson<JobEnvelope>(`${API}/api/previs/jobs/${jobId}`)
      .then((recovered) => {
        setJob(recovered);
        onRecover();
        if (["queued", "generating", "reviewing"].includes(recovered.job.status)) {
          void pollJob(jobId);
        }
      })
      .catch(() => window.localStorage.removeItem(STORED_JOB_KEY));
  }, []);

  async function createBrief(event: FormEvent) {
    event.preventDefault();
    if (!section || !sessionId) return;
    setActivity("briefing");
    setError("");
    try {
      const created = await apiJson<BriefEnvelope>(
        `${API}/api/research/${sessionId}/previs/briefs`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            board_section_title: section.title,
            shot_type: shotType,
            strictness,
            duration_seconds: duration,
            aspect_ratio: aspectRatio,
            reference_asset_ids: references,
          }),
        },
      );
      setBrief(created);
      setActivity("idle");
    } catch (reason) {
      setError(message(reason));
      setActivity("idle");
    }
  }

  async function generateClip() {
    if (!brief || !paidApproved) return;
    setActivity("submitting");
    setError("");
    try {
      const generated = await apiJson<JobEnvelope>(
        `${API}/api/previs/${brief.brief.shot_brief_id}/generate`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved: true,
            brief_fingerprint: brief.brief_fingerprint,
          }),
        },
      );
      setJob(generated);
      setPaidApproved(false);
      window.localStorage.setItem(STORED_JOB_KEY, generated.job.job_id);
      setActivity("idle");
      if (["queued", "generating"].includes(generated.job.status)) {
        await pollJob(generated.job.job_id);
      }
    } catch (reason) {
      setError(message(reason));
      setActivity("idle");
    }
  }

  async function pollJob(jobId: string) {
    setActivity("polling");
    for (let attempt = 0; attempt < 120; attempt += 1) {
      try {
        const current = await apiJson<JobEnvelope>(`${API}/api/previs/jobs/${jobId}`);
        setJob(current);
        if (!["queued", "generating", "reviewing"].includes(current.job.status)) {
          setActivity("idle");
          return;
        }
      } catch (reason) {
        setError(message(reason));
        setActivity("idle");
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, Math.min(2_000 + attempt * 250, 8_000)));
    }
    setError("Video generation is still running. Refresh later to recover this job.");
    setActivity("idle");
  }

  async function reviewClip() {
    if (!job) return;
    setActivity("reviewing");
    setError("");
    try {
      const reviewed = await apiJson<JobEnvelope>(
        `${API}/api/previs/jobs/${job.job.job_id}/review`,
        { method: "POST" },
      );
      setJob(reviewed);
      setActivity("idle");
    } catch (reason) {
      setError(message(reason));
      setActivity("idle");
    }
  }

  async function correctClip() {
    if (!job || !correctionApproved) return;
    setActivity("submitting");
    setError("");
    try {
      const corrected = await apiJson<JobEnvelope>(
        `${API}/api/previs/jobs/${job.job.job_id}/correct`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            approved: true,
            job_fingerprint: job.job_fingerprint,
          }),
        },
      );
      setJob(corrected);
      setCorrectionApproved(false);
      window.localStorage.setItem(STORED_JOB_KEY, corrected.job.job_id);
      if (["queued", "generating"].includes(corrected.job.status)) {
        await pollJob(corrected.job.job_id);
      } else {
        setActivity("idle");
      }
    } catch (reason) {
      setError(message(reason));
      setActivity("idle");
    }
  }

  function toggleReference(assetId: string) {
    setReferences((current) =>
      current.includes(assetId)
        ? current.filter((item) => item !== assetId)
        : current.length < 3
          ? [...current, assetId]
          : current,
    );
  }

  if (!open) return null;
  const referenceOptions = section?.assets.filter(
    (item) => item.asset.rights_status === "public_domain" && item.asset.thumbnail_path,
  ) ?? [];
  const working = activity !== "idle";

  return (
    <aside className="previs-panel" aria-label="Evidence-constrained previsualization">
      <button className="close" onClick={onClose} aria-label="Close previsualization">×</button>
      <p className="eyebrow">Research → previsualization</p>
      <h2>{section?.title ?? "Recovered previs job"}</h2>

      {!brief && !job && section && (
        <form className="previs-form" onSubmit={createBrief}>
          <p className="previs-intro">Gemini will turn this board section into a cited shot specification before any paid video request.</p>
          <div className="control-grid">
            <label>Shot type<select value={shotType} onChange={(event) => setShotType(event.target.value)}><option value="establishing_shot">Establishing shot</option><option value="travel_shot">Travel shot</option><option value="camp_scene">Camp scene</option><option value="landscape_plate">Landscape plate</option></select></label>
            <label>Evidence mode<select value={strictness} onChange={(event) => setStrictness(event.target.value)}><option value="strict">Strict</option><option value="interpretive">Interpretive</option></select></label>
            <label>Duration<select value={duration} onChange={(event) => setDuration(Number(event.target.value))}><option value={4}>4 seconds</option><option value={6}>6 seconds</option><option value={8}>8 seconds</option></select></label>
            <label>Frame<select value={aspectRatio} onChange={(event) => setAspectRatio(event.target.value)}><option value="16:9">Landscape · 16:9</option><option value="9:16">Portrait · 9:16</option></select></label>
          </div>
          <fieldset className="reference-picker">
            <legend>Public-domain visual references · up to 3</legend>
            {referenceOptions.length ? referenceOptions.map((item) => (
              <label key={item.asset.asset_id}>
                <input type="checkbox" checked={references.includes(item.asset.asset_id)} onChange={() => toggleReference(item.asset.asset_id)} />
                <span>{item.asset.title}</span>
              </label>
            )) : <p>No eligible cached references in this section. Text-to-video remains available when configured.</p>}
          </fieldset>
          <button type="submit" disabled={working}>{working ? "Building cited shot brief…" : "Create shot brief"}</button>
        </form>
      )}

      {brief && (
        <div className="shot-brief">
          <div className="previs-meta"><span>{brief.brief.strictness}</span><span>{brief.brief.duration_seconds}s</span><span>{brief.brief.aspect_ratio}</span><span>{brief.brief.producer_model}</span></div>
          <h3>{brief.brief.content.setting}</h3>
          <p>{brief.brief.content.action} {brief.brief.content.composition}</p>
          <div className="brief-split">
            <div><h4>Supported details</h4><ol>{brief.brief.content.supported_details.map((detail) => <li key={detail.detail}><strong>{detail.detail}</strong><small>{detail.passage_ids.join(" · ")}</small></li>)}</ol></div>
            <div><h4>Excluded</h4><ul>{brief.brief.content.excluded_details.map((item) => <li key={item}>{item}</li>)}</ul></div>
          </div>
          {brief.brief.content.interpretive_additions.length > 0 && <div className="interpretive-note"><strong>Interpretive additions</strong><p>{brief.brief.content.interpretive_additions.join(" · ")}</p></div>}
          {brief.blockers.length > 0 && <p className="previs-blocked">{brief.blockers.join(" ")}</p>}
          {brief.can_generate && !job && (
            <div className="paid-approval">
              <label><input type="checkbox" checked={paidApproved} onChange={(event) => setPaidApproved(event.target.checked)} /><span>I approve one paid Veo generation using this exact brief.</span></label>
              <button type="button" onClick={generateClip} disabled={!paidApproved || working}>{working ? "Starting Veo…" : `Generate ${brief.brief.duration_seconds}-second clip · est. $${brief.estimated_cost_usd?.toFixed(2)}`}</button>
            </div>
          )}
        </div>
      )}

      {job && (
        <div className="previs-output" aria-live="polite">
          <div className="generated-disclosure">{job.disclosure}</div>
          <div className="previs-meta"><span>{job.job.status}</span><span>{job.job.model}</span><span>generation {job.job.generation_count}/2</span><span>est. ${job.job.estimated_cost_usd.toFixed(2)}</span></div>
          {["queued", "generating", "reviewing"].includes(job.job.status) && <p className="previs-wait">{activity === "reviewing" ? "Gemini is checking visible details against the approved evidence…" : "Veo is generating the approved shot. This can take several minutes; the job is safe to leave and recover."}</p>}
          {job.job.safe_error && <p className="previs-blocked">{job.job.safe_error}</p>}
          {job.video_url && <video className="previs-video" controls preload="metadata" src={`${API}${job.video_url}`} />}
          {job.job.status === "complete" && job.video_url && !job.report && <button className="secondary-action" type="button" onClick={reviewClip} disabled={working}>{activity === "reviewing" ? "Reviewing visible details…" : "Review clip against evidence"}</button>}
          {job.report && (
            <div className="consistency-report">
              <p className="eyebrow">Historical consistency report</p>
              <h3>{job.report.overall_result.replaceAll("_", " ")}</h3>
              <ol>{job.report.findings.map((finding, index) => <li key={`${finding.visible_detail}-${index}`} className={finding.label}><span>{finding.label} · {finding.approximate_time_range}</span><strong>{finding.visible_detail}</strong><p>{finding.rationale}</p></li>)}</ol>
              {job.report.correction_instructions.length > 0 && job.job.generation_count < 2 && <div className="paid-approval"><label><input type="checkbox" checked={correctionApproved} onChange={(event) => setCorrectionApproved(event.target.checked)} /><span>I approve one paid correction using only this review.</span></label><button type="button" onClick={correctClip} disabled={!correctionApproved || working}>Generate corrected clip</button></div>}
            </div>
          )}
        </div>
      )}

      {error && <p className="error" role="alert">{error}</p>}
    </aside>
  );
}

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || "The previsualization request failed.");
  return payload as T;
}

function message(reason: unknown) {
  return reason instanceof Error ? reason.message : "The previsualization request failed.";
}
