"use client";

import { useEffect, useState } from "react";
import { API } from "./types";

/** One step of the ingestion path, as the API reports it for a corpus. */
type Stage = {
  key: string;
  label: string;
  state: "done" | "partial" | "empty";
  summary: string;
  counts: [string, number][];
  command: string;
};

type Window = { scope_id: string; title: string; span: string; captured: boolean };

type Pipeline = {
  corpus_id: string;
  title: string;
  description: string;
  status: string;
  display_policy: string;
  licenses: string[];
  sources: string[];
  stages: Stage[];
  windows: Window[];
  known_limitations: string[];
};

const STATE_LABEL: Record<Stage["state"], string> = {
  done: "complete",
  partial: "partial",
  empty: "not started",
};

const STEPS = [
  {
    title: "Bring a text in under a licence",
    body:
      "A source is registered with its edition, its publication year, and the rights that " +
      "govern display. Nothing is ingested whose provenance a person has not accepted.",
    command: "sourcecut-load-gutenberg · sourcecut-load-odyssey",
  },
  {
    title: "Parse it into citable units",
    body:
      "One parser per edition, because every text is addressed differently: the journals by " +
      "dated entry, the poem by book and line.",
    command: "pipelines/journals/*.py",
  },
  {
    title: "Segment and extract",
    body:
      "Passages carry their character offsets, and every observation records the exact span " +
      "it came from, so a claim can be checked against the text rather than trusted.",
    command: "sourcecut-extract-passages --source-id … --start-date … --end-date …",
  },
  {
    title: "Open it to research",
    body:
      "Curated windows give a plan somewhere to point. From there the same agent loop runs: " +
      "plan, retrieve, score coverage, widen once, report what the corpus could not support.",
    command: "sourcecut-capture-example \"…\" --out data/examples/<scope>.json",
  },
];

export default function ProjectShelf() {
  const [pipelines, setPipelines] = useState<Pipeline[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let live = true;
    fetch(`${API}/api/v1/pipelines`)
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("unavailable"))))
      .then((data) => live && setPipelines(data))
      .catch(() => live && setError("The corpus registry could not be reached."))
      .finally(() => undefined);
    return () => {
      live = false;
    };
  }, []);

  return (
    <div className="sourcecut cut-projects">
      <header className="cut-projects-head">
        <p className="label label-gold">Projects</p>
        <h1>Every corpus arrives the same way.</h1>
        <p className="cut-lede">
          A research board is the last step of a pipeline, not the first. These are the corpora
          SourceCut has taken through it, with the counts read back through the same read-only
          role the research path uses.
        </p>
      </header>

      {error && <p className="cut-error" role="alert">{error}</p>}

      {pipelines === null && !error && (
        <p className="cut-projects-pending" role="status">
          Reading the corpus registry…
        </p>
      )}

      {pipelines?.map((pipeline) => (
        <section key={pipeline.corpus_id} className="cut-project" aria-labelledby={pipeline.corpus_id}>
          <div className="cut-project-head">
            <div>
              <p className="label label-gold">{pipeline.corpus_id}</p>
              <h2 id={pipeline.corpus_id}>{pipeline.title}</h2>
              <p className="cut-project-desc">{pipeline.description}</p>
            </div>
            <div className="cut-project-rights">
              <span className={`cut-badge ${pipeline.status === "active" ? "covered" : "single_source"}`}>
                {pipeline.status}
              </span>
              <span className="label">{pipeline.display_policy.replaceAll("_", " ")}</span>
              {pipeline.licenses.map((license) => (
                <span key={license} className="label">{license}</span>
              ))}
            </div>
          </div>

          <ol className="cut-stages">
            {pipeline.stages.map((stage) => (
              <li key={stage.key} className={stage.state}>
                <div className="cut-stage-head">
                  <b>{stage.label}</b>
                  <span className="label">{STATE_LABEL[stage.state]}</span>
                </div>
                <p>{stage.summary}</p>
                {stage.counts.length > 0 && (
                  <div className="cut-stage-counts">
                    {stage.counts.map(([name, value]) => (
                      <span key={name}>
                        <b className="tabular">{value.toLocaleString()}</b> {name}
                      </span>
                    ))}
                  </div>
                )}
                {stage.command && <code>{stage.command}</code>}
              </li>
            ))}
          </ol>

          <div className="cut-project-foot">
            <div>
              <p className="label">Sources</p>
              <ul className="cut-project-list">
                {pipeline.sources.map((source) => <li key={source}>{source}</li>)}
              </ul>
            </div>
            <div>
              <p className="label">Research windows</p>
              <ul className="cut-project-windows">
                {pipeline.windows.map((window) => (
                  <li key={window.scope_id}>
                    {window.captured ? (
                      <a href={`/board/${window.scope_id}`}>{window.title}</a>
                    ) : (
                      <span>{window.title}</span>
                    )}
                    <span className="label tabular">{window.span}</span>
                  </li>
                ))}
              </ul>
            </div>
            {pipeline.known_limitations.length > 0 && (
              <div>
                <p className="label">Known limits</p>
                <ul className="cut-project-list">
                  {pipeline.known_limitations.map((limit) => <li key={limit}>{limit}</li>)}
                </ul>
              </div>
            )}
          </div>
        </section>
      ))}

      <section className="cut-project cut-project-new" aria-labelledby="new-project">
        <p className="label label-gold">Start a new project</p>
        <h2 id="new-project">A corpus is four steps and a rights decision.</h2>
        <ol className="cut-steps">
          {STEPS.map((step, index) => (
            <li key={step.title}>
              <span className="tabular">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <b>{step.title}</b>
                <p>{step.body}</p>
                <code>{step.command}</code>
              </div>
            </li>
          ))}
        </ol>
        <p className="cut-project-desc">
          The commands are the same ones that produced both corpora above. What differs between
          projects is the parser — every edition is addressed in its own way — and the windows a
          plan may choose.
        </p>
      </section>
    </div>
  );
}
