"use client";

import type { Pipeline } from "./ProjectDashboard";

/** What each project offers, in the words that corpus deserves. */
const PITCH: Record<string, { kind: string; line: string; entry: string }> = {
  "lewis-and-clark": {
    kind: "Dated journals · three diarists",
    line:
      "Ask for a scene and get a research board: verbatim passages with their character " +
      "offsets, which diarist wrote on which day, and rights-cleared Library of Congress " +
      "references.",
    entry: "Open the research boards",
  },
  odyssey: {
    kind: "A poem · one text, three versions",
    line:
      "Read the Greek beside two translations, cite by line, follow repeated formulae, and " +
      "see the voyage as competing proposals rather than one line on a map.",
    entry: "Open the reading room",
  },
};

function firstCount(pipeline: Pipeline, key: string): string {
  for (const stage of pipeline.stages) {
    for (const [name, value] of stage.counts) {
      if (name === key) return value.toLocaleString();
    }
  }
  return "—";
}

export default function CorpusLanding({ pipelines }: { pipelines: Pipeline[] }) {
  return (
    <main id="main-content" className="sourcecut">
      <header className="cut-slate">
        <div className="cut-slate-left">
          <a className="wordmark" href="/">SourceCut</a>
          <span className="cut-stamp">ARCHIVE</span>
          <span className="label">Evidence for production</span>
        </div>
        <div className="cut-slate-right">
          <span className="cut-pill">
            <span className="label">{pipelines.length} projects</span>
          </span>
          <span className="cut-pill live">
            <i />
            ClickHouse MCP · read-only
          </span>
        </div>
      </header>

      <div className="cut-shell">
        <section className="cut-frame" aria-labelledby="hero-title">
          <div className="cut-frame-inner">
            <div className="cut-frame-text">
              <p className="label label-gold">Primary sources, kept whole</p>
              <h1 id="hero-title">Research a scene against the record it came from.</h1>
              <p className="cut-lede">
                SourceCut takes a production brief and answers it out of a primary-source corpus:
                every claim resolves to a stored passage, every reference carries a rights
                decision a person accepted, and what the corpus cannot support is said out loud.
              </p>
              <div className="cut-reads">
                <div><b>Gemini on Vertex AI</b><em>· plans the research</em></div>
                <div><b>ClickHouse MCP</b><em>· read-only retrieval</em></div>
                <div><b>Exact character offsets</b><em>· span-verified quotes</em></div>
                <div><b>Item-level rights</b><em>· accepted by a person</em></div>
              </div>
            </div>

            {/* One of the archive's own references, credited the way every board
                credits one: title, maker, date, catalogue id, rights. */}
            <figure className="cut-plate">
              <a href="https://www.loc.gov/item/79692907/" target="_blank" rel="noreferrer">
                <img
                  src="/loc-79692907-track-map.jpg"
                  width={958}
                  height={1000}
                  alt="Detail of Samuel Lewis's 1814 engraving of William Clark's map of the expedition's track, showing the Pacific coast, the Columbia, and the Rocky Mountains."
                  loading="eager"
                />
              </a>
              <figcaption>
                <b>A map of Lewis and Clark's track across the western portion of North America</b>
                <span className="label tabular">
                  Samuel Lewis after William Clark · 1804–06 · loc:79692907 · public domain
                </span>
              </figcaption>
            </figure>
          </div>
        </section>

        <section className="cut-section" aria-labelledby="projects-title">
          <div className="cut-section-head">
            <div>
              <p className="label label-gold">Projects</p>
              <h2 id="projects-title">Two corpora, one pipeline.</h2>
            </div>
            <a className="label" href="/projects">How a corpus reaches a board →</a>
          </div>

          <div className="cut-corpus-grid">
            {pipelines.map((pipeline) => {
              const pitch = PITCH[pipeline.corpus_id];
              const passages = firstCount(pipeline, "passages");
              return (
                <a
                  className="cut-corpus"
                  key={pipeline.corpus_id}
                  href={`/project/${pipeline.corpus_id}`}
                >
                  <div className="cut-corpus-head">
                    <span className="label label-gold">{pitch?.kind ?? pipeline.corpus_id}</span>
                    <span className={`cut-badge ${pipeline.status === "active" ? "covered" : "single_source"}`}>
                      {pipeline.status}
                    </span>
                  </div>
                  <h3>{pipeline.title}</h3>
                  <p>{pitch?.line ?? pipeline.description}</p>

                  <div className="cut-corpus-figures">
                    <span>
                      <b className="tabular">{passages}</b> passages
                    </span>
                    <span>
                      <b className="tabular">{pipeline.windows.length}</b>{" "}
                      {pipeline.corpus_id === "lewis-and-clark" ? "windows" : "text"}
                    </span>
                    <span>
                      <b className="tabular">{pipeline.sources.length}</b> sources
                    </span>
                  </div>

                  <div className="cut-corpus-foot">
                    <span className="label">{pipeline.licenses[0]}</span>
                    <span className="label label-gold">{pitch?.entry ?? "Open"} →</span>
                  </div>
                </a>
              );
            })}
          </div>
        </section>

        <footer className="cut-footer">
          <div>
            <span className="label">Journals · Lewis, Clark and Gass · Gutenberg 8419</span>
            <span className="label">Odyssey · Perseus Digital Library · CC BY-SA</span>
            <span className="label">References · Library of Congress</span>
          </div>
          <a className="label label-gold" href="/projects">
            How a corpus reaches a board →
          </a>
        </footer>
      </div>
    </main>
  );
}
