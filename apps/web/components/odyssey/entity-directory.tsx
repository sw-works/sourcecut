"use client";
import { useEffect, useState } from "react";
import styles from "../../app/odyssey/odyssey.module.css";
import { fetchJson } from "../../lib/fetch-json";
const API = "/sourcecut-api/api/v1";
type Entity = {
  entity_id: string;
  entity_type: string;
  canonical_name: string;
  greek_name: string;
  aliases: string[];
  description: string;
  occurrence_count: number;
};
type Occurrence = {
  mention_id: string;
  surface: string;
  version_id: string;
  book: number;
  line_start: number;
  line_end: number;
  citation: string;
  original_text: string;
};
type Profile = {
  entity: Entity;
  occurrences: Occurrence[];
  annotation_notice: string;
};
type Edge = {
  source_entity_id: string;
  target_entity_id: string;
  source_type: string;
  target_type: string;
  shared_unit_count: number;
};
export default function EntityDirectory({
  initialId = "",
}: {
  initialId?: string;
}) {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [type, setType] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    fetchJson<Entity[]>(
      `${API}/entities`,
      undefined,
      "Entities are unavailable.",
    )
      .then((data) => {
        setEntities(data);
        setError("");
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!initialId) return;
    Promise.all([
      fetchJson<Profile>(
        `${API}/entities/${initialId}`,
        undefined,
        "Entity details are unavailable.",
      ),
      fetchJson<Edge[]>(
        `${API}/relationships?entity_id=${initialId}`,
        undefined,
        "Entity relationships are unavailable.",
      ),
    ])
      .then(([p, e]) => {
        setProfile(p);
        setEdges(e);
        setError("");
      })
      .catch((reason: Error) => setError(reason.message));
  }, [initialId]);
  const types = [...new Set(entities.map((item) => item.entity_type))];
  return (
    <div className={styles.entityPage}>
      <header className={styles.entityHero}>
        <p className={styles.eyebrow}>Names across witnesses</p>
        <h1>
          People, powers,
          <br />
          places, things.
        </h1>
        <p>
          Odysseus and Ulysses resolve to one identity. Every occurrence remains
          attached to its exact edition and surface form.
        </p>
      </header>
      {error && <p role="alert">{error}</p>}
      {loading && (
        <p className={styles.surfaceStatus}>Indexing exact name matches…</p>
      )}
      {profile ? (
        <ProfileView profile={profile} edges={edges} />
      ) : (
        <>
          <nav className={styles.entityTypes}>
            {
              <button aria-pressed={!type} onClick={() => setType("")}>
                All
              </button>
            }
            {types.map((item) => (
              <button
                key={item}
                aria-pressed={type === item}
                onClick={() => setType(item)}
              >
                {item}
              </button>
            ))}
          </nav>
          <section className={styles.entityGrid}>
            {entities
              .filter((item) => !type || item.entity_type === type)
              .map((item) => (
                <a
                  href={`/odyssey/entities/${item.entity_id}`}
                  key={item.entity_id}
                >
                  <span>{item.entity_type}</span>
                  <h2>{item.canonical_name}</h2>
                  <b lang="grc">{item.greek_name}</b>
                  <p>{item.description}</p>
                  <small>{item.occurrence_count} exact alias matches →</small>
                </a>
              ))}
          </section>
          {!loading && entities.length === 0 && !error && (
            <p className={styles.surfaceStatus}>
              No reviewed entities are available.
            </p>
          )}
        </>
      )}
    </div>
  );
}
function ProfileView({ profile, edges }: { profile: Profile; edges: Edge[] }) {
  const e = profile.entity;
  return (
    <>
      <section className={styles.entityProfile}>
        <div>
          <a href="/odyssey/entities">← All entities</a>
          <p className={styles.eyebrow}>{e.entity_type}</p>
          <h2>{e.canonical_name}</h2>
          <h3 lang="grc">{e.greek_name}</h3>
          <p>{e.description}</p>
          <dl>
            <dt>Translation aliases</dt>
            <dd>{e.aliases.join(" · ")}</dd>
          </dl>
        </div>
        <div>
          <h3>Exact occurrences</h3>
          <p>{profile.annotation_notice}</p>
          <ol>
            {profile.occurrences.slice(0, 80).map((item) => (
              <li key={item.mention_id}>
                <a
                  href={`/odyssey/read/${item.book}?version=${item.version_id}&lines=${item.line_start}-${item.line_end}`}
                >
                  {item.citation} · {item.version_id}
                </a>
                <p>{item.original_text}</p>
                <strong>{item.surface}</strong>
              </li>
            ))}
          </ol>
        </div>
      </section>
      <section className={styles.relationshipPanel}>
        <p className={styles.eyebrow}>Retrieval graph</p>
        <h2>Shared exact units</h2>
        <p>
          Co-occurrence helps navigate the text. It does not establish a social
          or historical relationship.
        </p>
        <div>
          {edges.map((edge) => (
            <article key={`${edge.source_entity_id}:${edge.target_entity_id}`}>
              <span>
                {edge.source_type} ↔ {edge.target_type}
              </span>
              <strong>
                {edge.source_entity_id} / {edge.target_entity_id}
              </strong>
              <small>{edge.shared_unit_count} shared units</small>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
