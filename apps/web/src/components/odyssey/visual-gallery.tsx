"use client";
import { useEffect, useState } from "react";
import styles from "../../styles/odyssey.module.css";
import { fetchJson } from "../../lib/fetch-json";
type Asset = {
  asset_id: string;
  title: string;
  creators: string[];
  object_date: string;
  culture: string;
  medium: string;
  institution: string;
  object_id: string;
  source_url: string;
  rights_status: string;
  image_rights_status: string;
  cached_image_path: string;
  relationship_class: string;
  production_use: string;
  limitations: string;
  confidence: string;
  verification_status: string;
  evidence_ids: string[];
};
const API = "/sourcecut-api/api/v1";
const relationships = [
  "ANCIENT_REPRESENTATION",
  "ANCIENT_COMPARATIVE_OBJECT",
  "LATER_CLASSICAL_RECEPTION",
  "POST_CLASSICAL_RECEPTION",
];
export default function VisualGallery() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [query, setQuery] = useState("");
  const [relationship, setRelationship] = useState("");
  const [selected, setSelected] = useState<Asset | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      fetchJson<Asset[]>(
        `${API}/search/assets`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            query,
            relationships: relationship ? [relationship] : [],
            public_only: true,
          }),
        },
        "Visual records are unavailable.",
      )
        .then((data) => {
          setAssets(data);
          setError("");
        })
        .catch((reason: Error) => {
          if (reason.name !== "AbortError") setError(reason.message);
        })
        .finally(() => setLoading(false));
    }, 150);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, relationship]);
  return (
    <div className={styles.visualPage}>
      <header>
        <p className={styles.eyebrow}>Objects are not witnesses to events</p>
        <h1>
          Ancient image.
          <br />
          Later imagination.
        </h1>
        <p>
          Every item states whether it is ancient representation, comparative
          material, or later reception—and what it cannot prove.
        </p>
      </header>
      {error && <p role="alert">{error}</p>}
      <form className={styles.visualFilters}>
        <label>
          Search records
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Circe, papyrus, Penelope…"
          />
        </label>
        <label>
          Relationship
          <select
            value={relationship}
            onChange={(e) => setRelationship(e.target.value)}
          >
            <option value="">All public relationships</option>
            {relationships.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
      </form>
      {loading && (
        <p className={styles.surfaceStatus}>Reviewing rights-safe records…</p>
      )}
      <section className={styles.assetGrid}>
        {assets.map((asset) => (
          <button key={asset.asset_id} onClick={() => setSelected(asset)}>
            <div>
              {asset.cached_image_path ? (
                <img src={asset.cached_image_path} alt="" />
              ) : (
                <span>
                  Metadata only
                  <br />
                  {asset.image_rights_status}
                </span>
              )}
            </div>
            <small>{asset.relationship_class.replaceAll("_", " ")}</small>
            <h2>{asset.title}</h2>
            <p>
              {asset.object_date} · {asset.medium}
            </p>
            <strong>{asset.verification_status.replaceAll("_", " ")}</strong>
          </button>
        ))}
      </section>
      {!loading && assets.length === 0 && !error && (
        <p className={styles.surfaceStatus}>
          No public records match these filters.
        </p>
      )}
      {selected && (
        <aside className={styles.assetDrawer}>
          <button onClick={() => setSelected(null)}>×</button>
          <p className={styles.eyebrow}>
            {selected.relationship_class.replaceAll("_", " ")}
          </p>
          <h2>{selected.title}</h2>
          {selected.cached_image_path && (
            <img src={selected.cached_image_path} alt={selected.title} />
          )}
          <dl>
            <div>
              <dt>Institution</dt>
              <dd>{selected.institution}</dd>
            </div>
            <div>
              <dt>Object ID</dt>
              <dd>{selected.object_id}</dd>
            </div>
            <div>
              <dt>Date / culture</dt>
              <dd>
                {selected.object_date} · {selected.culture}
              </dd>
            </div>
            <div>
              <dt>Medium</dt>
              <dd>{selected.medium}</dd>
            </div>
            <div>
              <dt>Record rights</dt>
              <dd>{selected.rights_status}</dd>
            </div>
            <div>
              <dt>Image rights</dt>
              <dd>{selected.image_rights_status}</dd>
            </div>
          </dl>
          <h3>Research use</h3>
          <p>{selected.production_use}</p>
          <h3>Limitations</h3>
          <p>{selected.limitations}</p>
          <p>Linked evidence: {selected.evidence_ids.join(" · ")}</p>
          <a href={selected.source_url} target="_blank" rel="noreferrer">
            Open museum record ↗
          </a>
        </aside>
      )}
    </div>
  );
}
