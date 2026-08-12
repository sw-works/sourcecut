"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

const API = "/sourcecut-api/api/v1";
type Mode = "exact" | "normalized" | "form" | "lemma" | "english";
type Match = { char_start: number; char_end: number; token_id: string };
type Token = { token_id: string; surface: string; lemma: string; part_of_speech: string; morphology: Record<string, string>; annotation_source: string; annotation_version: string; annotation_confidence: number; review_status: string; occurrence_count: number };
type Hit = { text_unit_id: string; version_id: string; citation: string; cts_urn: string; book: number; line_start: number; line_end: number; text: string; matches: Match[]; token: Token | null };
type SearchResponse = { query: string; mode: Mode; interpretation: string; hits: Hit[]; facets: Record<string, Record<string, number>>; next_cursor: string | null; warnings: string[] };
type Formula = { formula_id: string; display_formula: string; ngram_size: number; occurrence_count: number; occurrences: { book: number; line_start: number; line_end: number }[]; status: string };
type Saved = { saved_search_id: string; name: string; search: { query: string; mode: Mode }; created_at: string };

export default function SearchWorkbench() {
  const [query, setQuery] = useState("πολύτροπος");
  const [mode, setMode] = useState<Mode>("lemma");
  const [books, setBooks] = useState<number[]>([]);
  const [partOfSpeech, setPartOfSpeech] = useState("");
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [selectedToken, setSelectedToken] = useState<Token | null>(null);
  const [frequency, setFrequency] = useState<{ key: string; count: number }[]>([]);
  const [formulae, setFormulae] = useState<Formula[]>([]);
  const [coLeft, setCoLeft] = useState("ἀνήρ");
  const [coRight, setCoRight] = useState("πολύτροπος");
  const [cooccurrences, setCooccurrences] = useState<Record<string, unknown>[]>([]);
  const [saved, setSaved] = useState<Saved[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { fetch(`${API}/saved-searches`).then((response) => response.json()).then(setSaved).catch(() => undefined); }, []);

  const request = useMemo(() => ({
    query, mode, books, part_of_speech: partOfSpeech ? [partOfSpeech] : [],
    version_ids: mode === "english" ? ["odyssey-perseus-eng3", "odyssey-perseus-eng4"] : ["odyssey-perseus-grc2"],
    page_size: 25,
  }), [query, mode, books, partOfSpeech]);

  async function search(event?: FormEvent) {
    event?.preventDefault(); setBusy(true); setError(""); setSelectedToken(null);
    try {
      const response = await fetch(`${API}/search/text`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
      if (!response.ok) throw new Error((await response.json()).detail ?? "Search failed.");
      const next = await response.json() as SearchResponse; setResult(next);
      if (["lemma", "form", "normalized"].includes(mode)) {
        const frequencyResponse = await fetch(`${API}/search/frequency`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, mode: mode === "lemma" ? "lemma" : "form" }) });
        if (frequencyResponse.ok) setFrequency((await frequencyResponse.json()).buckets);
      } else setFrequency([]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Search failed."); }
    finally { setBusy(false); }
  }

  async function loadMore() {
    if (!result?.next_cursor) return;
    const response = await fetch(`${API}/search/text`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...request, cursor: result.next_cursor }) });
    if (!response.ok) { setError("The next result page could not be loaded."); return; }
    const page = await response.json() as SearchResponse;
    setResult({ ...page, hits: [...result.hits, ...page.hits] });
  }

  async function inspectToken(token: Token) {
    const response = await fetch(`${API}/tokens/${token.token_id}`);
    setSelectedToken(response.ok ? await response.json() : token);
  }

  async function findFormulae() {
    const response = await fetch(`${API}/search/formulae`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ query, page_size: 20 }) });
    if (response.ok) setFormulae(await response.json());
  }

  async function findCooccurrences(event: FormEvent) {
    event.preventDefault();
    const response = await fetch(`${API}/search/cooccurrences`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ left_lemma: coLeft, right_lemma: coRight, window_lines: 5, books }) });
    if (response.ok) setCooccurrences(await response.json());
  }

  async function saveSearch() {
    const response = await fetch(`${API}/saved-searches`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: `${query} · ${mode}`, search: request }) });
    if (response.ok) {
      const item = await response.json() as Saved;
      setSaved((current) => [...current, item]);
    }
  }

  function toggleBook(book: number) { setBooks((current) => current.includes(book) ? current.filter((item) => item !== book) : [...current, book]); }
  const maxFrequency = Math.max(1, ...frequency.map((item) => item.count));

  return <div className={styles.searchWorkbench}>
    <header className={styles.searchHero}><p className={styles.eyebrow}>Lexical workbench</p><h1>Search the words,<br />keep the witnesses.</h1><p>Exact text and imported linguistic annotations remain visibly separate. Every occurrence opens at a resolved line.</p></header>
    <form className={styles.searchComposer} onSubmit={search}>
      <label htmlFor="odyssey-search">Greek form, lemma, or English wording</label>
      <div><input id="odyssey-search" value={query} onChange={(event) => setQuery(event.target.value)} required /><button disabled={busy}>{busy ? "Searching…" : "Search"}</button></div>
      <fieldset><legend>Interpret as</legend>{(["exact", "normalized", "form", "lemma", "english"] as Mode[]).map((item) => <label key={item}><input type="radio" name="search-mode" checked={mode === item} onChange={() => setMode(item)} /><span>{item}</span></label>)}</fieldset>
    </form>
    <aside className={styles.searchFilters} aria-label="Search filters"><h2>Scope</h2><label>Part of speech<select value={partOfSpeech} onChange={(event) => setPartOfSpeech(event.target.value)} disabled={mode === "english" || mode === "exact"}><option value="">Any annotated class</option>{["noun", "verb", "adjective", "adverb", "pronoun", "particle"].map((item) => <option key={item}>{item}</option>)}</select></label><fieldset><legend>Books</legend><div className={styles.bookChips}>{Array.from({ length: 24 }, (_, index) => index + 1).map((book) => <label key={book}><input type="checkbox" checked={books.includes(book)} onChange={() => toggleBook(book)} /><span>{book}</span></label>)}</div></fieldset><div className={styles.pendingFilters}><span>Speaker</span><span>Entity</span><span>Narrative level</span><p>Available when their reviewed annotation releases are loaded; the API refuses to ignore these filters.</p></div>
      <h2>Saved</h2>{saved.length === 0 ? <p>No saved searches in this application session.</p> : <ul className={styles.savedList}>{saved.map((item) => <li key={item.saved_search_id}><button onClick={() => { setQuery(item.search.query); setMode(item.search.mode); }}>{item.name}</button></li>)}</ul>}
    </aside>
    <section className={styles.searchResults} aria-live="polite">
      {error && <p className={styles.readerError} role="alert">{error}</p>}
      {!result && !error && <div className={styles.searchEmpty}><span>ἀ</span><h2>Begin with a word.</h2><p>Try <button onClick={() => { setQuery("πολύτροπος"); setMode("lemma"); }}>πολύτροπος as lemma</button> or search an identified translation for “wine-dark sea.”</p></div>}
      {result && <><header className={styles.resultHeader}><div><p className={styles.eyebrow}>{result.hits.length} visible occurrences</p><h2>{result.query}</h2><p>{result.interpretation}</p></div><button onClick={saveSearch}>Save search</button></header>{result.warnings.map((warning) => <p className={styles.annotationNotice} key={warning}><strong>Derived annotation</strong>{warning}</p>)}
        {frequency.length > 0 && <section className={styles.frequencyChart} aria-labelledby="frequency-title"><div><h3 id="frequency-title">Frequency by book</h3><span>Exact annotated occurrences</span></div><ol>{frequency.map((item) => <li key={item.key}><span>{item.key}</span><i style={{ height: `${Math.max(4, (item.count / maxFrequency) * 100)}%` }} /><strong>{item.count}</strong></li>)}</ol></section>}
        {result.hits.length === 0 ? <div className={styles.noResults}><h3>No qualifying lines.</h3><p>The query was interpreted as: {result.interpretation} Remove a book or morphology filter, or switch modes.</p></div> : <ol className={styles.hitList}>{result.hits.map((hit) => <li key={`${hit.text_unit_id}-${hit.matches[0]?.token_id ?? "text"}`}><Link href={`/odyssey/read/${hit.book}?version=${hit.version_id}&lines=${hit.line_start}-${hit.line_end}`}>{hit.citation}</Link><p>{highlight(hit.text, hit.matches)}</p>{hit.token && <button className={styles.tokenTag} onClick={() => inspectToken(hit.token!)}><span>{hit.token.surface}</span>{hit.token.lemma || "unannotated"} · {hit.token.part_of_speech}</button>}<small>{hit.version_id}</small></li>)}</ol>}
        {result.next_cursor && <button className={styles.loadMore} onClick={loadMore}>Load next 25</button>}
        <section className={styles.patternTools}><article><p className={styles.eyebrow}>Exact pattern finder</p><h3>Recurring formulae</h3><p>Compare repeated 2–5-token sequences. These are retrieval aids, not interpretive claims.</p><button onClick={findFormulae}>Find patterns containing “{query}”</button>{formulae.map((item) => <details key={item.formula_id}><summary><span lang="grc">{item.display_formula}</span><strong>{item.occurrence_count}</strong></summary><p>{item.status} · {item.ngram_size}-token sequence</p>{item.occurrences.slice(0, 8).map((occurrence) => <Link key={`${occurrence.book}.${occurrence.line_start}`} href={`/odyssey/read/${occurrence.book}?lines=${occurrence.line_start}-${occurrence.line_end}`}>Od. {occurrence.book}.{occurrence.line_start}</Link>)}</details>)}</article>
          <article><p className={styles.eyebrow}>Line-window query</p><h3>Lemma co-occurrence</h3><form onSubmit={findCooccurrences}><label>First lemma<input value={coLeft} onChange={(event) => setCoLeft(event.target.value)} /></label><label>Second lemma<input value={coRight} onChange={(event) => setCoRight(event.target.value)} /></label><button>Find within five lines</button></form>{cooccurrences.length > 0 && <p>{cooccurrences.length} exact token pairings. <strong>Retrieval context only—not evidence of a relationship.</strong></p>}</article></section>
      </>}
    </section>
    {selectedToken && <aside className={styles.tokenPopover} aria-label="Token analysis"><button aria-label="Close token analysis" onClick={() => setSelectedToken(null)}>×</button><p className={styles.eyebrow}>Derived token analysis</p><h2 lang="grc">{selectedToken.surface}</h2><p className={styles.tokenLemma} lang="grc">{selectedToken.lemma || "No aligned lemma"}</p><dl><div><dt>Class</dt><dd>{selectedToken.part_of_speech}</dd></div>{Object.entries(selectedToken.morphology).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value}</dd></div>)}<div><dt>Occurrences</dt><dd>{selectedToken.occurrence_count}</dd></div><div><dt>Status</dt><dd>{selectedToken.review_status}</dd></div></dl><footer><strong>{selectedToken.annotation_source}</strong><span>{selectedToken.annotation_version} · confidence {selectedToken.annotation_confidence.toFixed(2)}</span><p>No lexicon gloss is shown without a pinned gloss source.</p></footer></aside>}
  </div>;
}

function highlight(text: string, matches: Match[]) {
  if (!matches.length) return text;
  const sorted = [...matches].sort((a, b) => a.char_start - b.char_start); const result: React.ReactNode[] = []; let cursor = 0;
  sorted.forEach((match, index) => { result.push(text.slice(cursor, match.char_start)); result.push(<mark key={`${match.char_start}-${index}`}>{text.slice(match.char_start, match.char_end)}</mark>); cursor = match.char_end; }); result.push(text.slice(cursor)); return result;
}
