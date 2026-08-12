"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import styles from "../../app/odyssey/odyssey.module.css";
const API = "/sourcecut-api/api/v1";
type Theme = {
  theme_id: string;
  title: string;
  description: string;
  aliases: string[];
  passage_count: number;
};
type Passage = {
  theme_passage_id: string;
  rationale: string;
  evidence_class: string;
  book: number;
  line_start: number;
  line_end: number;
  citation: string;
  original_text: string;
};
export default function ThemeAtlas() {
  const [themes, setThemes] = useState<Theme[]>([]);
  const [selected, setSelected] = useState<{
    theme: Theme;
    passages: Passage[];
    editorial_notice: string;
  } | null>(null);
  useEffect(() => {
    fetch(`${API}/themes`)
      .then((r) => r.json())
      .then(setThemes);
  }, []);
  async function open(id: string) {
    const r = await fetch(`${API}/themes/${id}`);
    if (r.ok) setSelected(await r.json());
  }
  return (
    <div className={styles.themePage}>
      <header>
        <p className={styles.eyebrow}>Curated interpretive index</p>
        <h1>
          Twelve threads
          <br />
          through the poem.
        </h1>
        <p>
          Theme links expose an editorial scope and an exact anchor passage.
          They are interpretations, never hidden facts.
        </p>
      </header>
      <section>
        {themes.map((item, index) => (
          <button key={item.theme_id} onClick={() => open(item.theme_id)}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <h2>{item.title}</h2>
            <p>{item.description}</p>
            <small>{item.passage_count} curated anchor</small>
          </button>
        ))}
      </section>
      {selected && (
        <aside className={styles.themeDrawer}>
          <button onClick={() => setSelected(null)}>×</button>
          <p className={styles.eyebrow}>Curated theme</p>
          <h2>{selected.theme.title}</h2>
          <p>{selected.theme.description}</p>
          <strong>{selected.editorial_notice}</strong>
          {selected.passages.map((p) => (
            <article key={p.theme_passage_id}>
              <span>{p.evidence_class}</span>
              <blockquote>{p.original_text}</blockquote>
              <p>{p.rationale}</p>
              <Link
                href={`/odyssey/read/${p.book}?lines=${p.line_start}-${p.line_end}`}
              >
                {p.citation} →
              </Link>
            </article>
          ))}
        </aside>
      )}
    </div>
  );
}
