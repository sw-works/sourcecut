"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

const API = "/sourcecut-api/api/v1";
const GREEK = "odyssey-perseus-grc2";
const TRANSLATIONS = [
  { id: "odyssey-perseus-eng3", short: "Murray 1919" },
  { id: "odyssey-perseus-eng4", short: "Butler, revised" },
];
type Mode = "greek" | "translation" | "parallel" | "interlinear";
type Unit = { text_unit_id: string; citation: string; cts_urn: string; book: number; line_start: number; line_end: number; text: string };
type TextRange = {
  version_id: string; version_label: string; language: string; book: number; line_start: number;
  line_end: number; cts_urn: string; bibliographic_description: string; attribution: string;
  source_url: string; license_name: string; license_url: string; units: Unit[];
};
type Parallel = { source: TextRange; targets: TextRange[]; warning: string };
type Selection = { start: number; end: number };

function browserInitialRange(
  fromLine: number,
  toLine: number,
  selection: Selection | null,
) {
  if (typeof window === "undefined") return { fromLine, toLine, selection };
  const match = /^(\d+)-(\d+)$/.exec(new URLSearchParams(window.location.search).get("lines") ?? "");
  if (!match) return { fromLine, toLine, selection };
  const selectedStart = Number(match[1]);
  const selectedEnd = Math.min(Number(match[2]), selectedStart + 199);
  const contextStart = Math.max(
    1,
    selectedStart - Math.min(12, 199 - (selectedEnd - selectedStart)),
  );
  return {
    fromLine: contextStart,
    toLine: Math.max(contextStart, Math.min(Math.max(selectedEnd, contextStart + 79), contextStart + 199)),
    selection: { start: selectedStart, end: selectedEnd },
  };
}

async function responseError(response: Response, fallback: string) {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

export default function TextReader({ initialBook, initialFromLine, initialToLine, initialSelection }: {
  initialBook: number; initialFromLine: number; initialToLine: number; initialVersion: string;
  initialSelection: Selection | null;
}) {
  const [initialRange] = useState(() =>
    browserInitialRange(initialFromLine, initialToLine, initialSelection),
  );
  const [book, setBook] = useState(initialBook);
  const [fromLine, setFromLine] = useState(initialRange.fromLine);
  const [toLine, setToLine] = useState(initialRange.toLine);
  const [targets, setTargets] = useState([TRANSLATIONS[0].id]);
  const [mode, setMode] = useState<Mode>("parallel");
  const [data, setData] = useState<Parallel | null>(null);
  const [selection, setSelection] = useState<Selection | null>(initialRange.selection);
  const [anchor, setAnchor] = useState<number | null>(null);
  const [reference, setReference] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState("");
  const lineRefs = useRef(new Map<number, HTMLButtonElement>());

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({ from_line: String(fromLine), to_line: String(toLine) });
    targets.forEach((target) => query.append("targets", target));
    setLoading(true); setError("");
    fetch(`${API}/text/${GREEK}/${book}/parallel?${query}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(await responseError(response, "Text could not be loaded."));
        return response.json() as Promise<Parallel>;
      })
      .then(setData)
      .catch((reason) => { if (reason.name !== "AbortError") setError(String(reason.message ?? reason)); })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [book, fromLine, toLine, targets]);

  const selectedUnits = useMemo(() => data?.source.units.filter((unit) =>
    selection && unit.line_end >= selection.start && unit.line_start <= selection.end,
  ) ?? [], [data, selection]);

  function changeBook(next: number) {
    setBook(next); setFromLine(1); setToLine(80); setSelection(null); setAnchor(null);
    window.history.replaceState(null, "", `/odyssey/read/${next}`);
  }

  function chooseLine(unit: Unit) {
    if (anchor === null) {
      setAnchor(unit.line_start); setSelection({ start: unit.line_start, end: unit.line_end });
    } else {
      setSelection({ start: Math.min(anchor, unit.line_start), end: Math.max(anchor, unit.line_end) });
      setAnchor(null);
    }
  }

  function navigateLine(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const unit = data?.source.units[index + (event.key === "ArrowDown" ? 1 : -1)];
    if (unit) lineRefs.current.get(unit.line_start)?.focus();
  }

  async function resolveReference(event: FormEvent) {
    event.preventDefault(); setError("");
    const query = new URLSearchParams({ reference, version_id: GREEK });
    const response = await fetch(`${API}/text/resolve?${query}`);
    if (!response.ok) { setError(await responseError(response, "Citation could not be resolved.")); return; }
    const resolved = await response.json() as { book: number; line_start: number; line_end: number; canonical_url: string };
    const span = resolved.line_end - resolved.line_start;
    const contextStart = Math.max(1, resolved.line_start - Math.min(12, 199 - span));
    setBook(resolved.book); setFromLine(contextStart); setToLine(Math.max(resolved.line_end, contextStart + 79));
    setSelection({ start: resolved.line_start, end: resolved.line_end }); setAnchor(null);
    window.history.replaceState(null, "", resolved.canonical_url);
  }

  function toggleTarget(id: string) {
    setTargets((current) => current.includes(id)
      ? (current.length === 1 ? current : current.filter((item) => item !== id))
      : [...current, id]);
  }

  async function copy(label: string, value: string) {
    await navigator.clipboard.writeText(value); setCopied(label);
    window.setTimeout(() => setCopied(""), 1800);
  }

  function createClaimDraft() {
    if (!data || selectedUnits.length === 0) return;
    window.sessionStorage.setItem("odyssey-claim-draft", JSON.stringify({
      evidence: selectedUnits.map((unit) => {
        const normalizedQuote = unit.text.normalize("NFC");
        return {
        support_role: "supports",
        source_kind: "text_span",
        source_record_id: unit.text_unit_id,
        version_id: data.source.version_id,
        source_quote: normalizedQuote,
        source_start: 0,
        source_end: Array.from(normalizedQuote).length,
        citation: unit.citation,
        };
      }),
    }));
    window.location.href = "/odyssey/claims?compose=1";
  }

  const selectedStart = selection?.start ?? 0;
  const selectedEnd = selection?.end ?? 0;
  const shortCitation = selection ? `Homer, Od. ${book}.${selectedStart}${selectedEnd === selectedStart ? "" : `–${selectedEnd}`}` : "";
  const ctsBase = data?.source.cts_urn.split(":").slice(0, -1).join(":") ?? "";
  const cts = selection ? `${ctsBase}:${book}.${selectedStart}${selectedEnd === selectedStart ? "" : `-${book}.${selectedEnd}`}` : "";
  const shareUrl = selection && typeof window !== "undefined" ? `${window.location.origin}/odyssey/read/${book}?version=${GREEK}&lines=${selectedStart}-${selectedEnd}` : "";

  return (
    <div className={styles.reader}>
      <aside className={styles.readerRail} aria-label="Reader controls">
        <p className={styles.eyebrow}>Canonical text</p>
        <h1>Book {book}</h1>
        <label>Book<select value={book} onChange={(event) => changeBook(Number(event.target.value))}>
          {Array.from({ length: 24 }, (_, index) => <option key={index + 1} value={index + 1}>Book {index + 1}</option>)}
        </select></label>
        <form className={styles.citationForm} onSubmit={resolveReference}>
          <label htmlFor="citation">Go to citation or CTS URN</label>
          <div><input id="citation" value={reference} onChange={(event) => setReference(event.target.value)} placeholder="Od. 9.216–230" required /><button>Go</button></div>
        </form>
        <fieldset className={styles.modePicker}><legend>Reading mode</legend>
          {(["greek", "translation", "parallel", "interlinear"] as Mode[]).map((item) =>
            <label key={item}><input type="radio" name="mode" checked={mode === item} onChange={() => setMode(item)} /><span>{item}</span></label>)}
        </fieldset>
        <fieldset className={styles.translationPicker}><legend>Translations</legend>
          {TRANSLATIONS.map((item) => <label key={item.id}><input type="checkbox" checked={targets.includes(item.id)} onChange={() => toggleTarget(item.id)} /><span>{item.short}</span></label>)}
        </fieldset>
        <fieldset className={styles.layerPicker} disabled><legend>Reviewed annotation layers</legend>
          <label><input type="checkbox" /><span>Claims</span></label><label><input type="checkbox" /><span>Entities</span></label>
          <label><input type="checkbox" /><span>Speech</span></label><label><input type="checkbox" /><span>Places</span></label>
          <small>Layers activate when their reviewed releases are loaded.</small>
        </fieldset>
      </aside>

      <section className={styles.textStage} aria-busy={loading}>
        <header className={styles.textHeader}>
          <div><p className={styles.eyebrow}>Lines {fromLine}–{toLine}</p><h2>{data?.source.version_label ?? "Greek edition"}</h2></div>
          <div className={styles.contextNav}>
            <button disabled={fromLine === 1 || loading} onClick={() => { const start = Math.max(1, fromLine - 80); setFromLine(start); setToLine(start + 79); }}>← Earlier</button>
            <button disabled={loading} onClick={() => { const start = toLine + 1; setFromLine(start); setToLine(start + 79); }}>Later →</button>
          </div>
        </header>
        {error && <p className={styles.readerError} role="alert">{error}</p>}
        {loading && <div className={styles.loading} aria-live="polite">Resolving pinned text…</div>}
        {data && !loading && <>
          <p className={styles.readerInstruction}>Select a line, then another line, to cite a contiguous range. Use ↑ and ↓ to move between line controls.</p>
          <div className={`${styles.textGrid} ${styles[mode]}`}>
            {mode !== "translation" && <TextColumn title="Greek" range={data.source} selection={selection} chooseLine={chooseLine} navigateLine={navigateLine} lineRefs={lineRefs} />}
            {(mode === "translation" || mode === "parallel") && data.targets.map((target) =>
              <TextColumn key={target.version_id} title={target.version_label} range={target} selection={selection} />)}
            {mode === "interlinear" && <Interlinear greek={data.source} translations={data.targets} selection={selection} chooseLine={chooseLine} navigateLine={navigateLine} lineRefs={lineRefs} />}
          </div>
          <footer className={styles.licenseNotice}>
            <p><strong>{data.source.attribution}</strong> {data.source.bibliographic_description}</p>
            <p><a href={data.source.source_url} target="_blank" rel="noreferrer">Pinned source</a> · <a href={data.source.license_url} target="_blank" rel="noreferrer">{data.source.license_name}</a></p>
            <small>{data.warning}</small>
          </footer>
        </>}
      </section>

      {selection && data && <aside className={styles.citationDrawer} aria-label="Citation drawer">
        <button className={styles.drawerClose} aria-label="Close citation drawer" onClick={() => { setSelection(null); setAnchor(null); }}>×</button>
        <p className={styles.eyebrow}>Exact selected span</p><h2>{shortCitation}</h2>
        <blockquote>{selectedUnits.map((unit) => unit.text).join(" ")}</blockquote>
        <dl><div><dt>Edition</dt><dd>{data.source.version_label}</dd></div><div><dt>CTS URN</dt><dd>{cts}</dd></div></dl>
        <div className={styles.copyGrid}>
          <button onClick={createClaimDraft}>Create claim from span</button>
          <button onClick={() => copy("short citation", shortCitation)}>Copy short citation</button>
          <button onClick={() => copy("bibliography", `${data.source.bibliographic_description} ${shortCitation}.`)}>Copy full citation</button>
          <button onClick={() => copy("CTS URN", cts)}>Copy CTS URN</button>
          <button onClick={() => copy("share URL", shareUrl)}>Copy share URL</button>
        </div>
        <p className={styles.copyStatus} aria-live="polite">{copied ? `Copied ${copied}.` : ""}</p>
      </aside>}
    </div>
  );
}

function TextColumn({ title, range, selection, chooseLine, navigateLine, lineRefs }: {
  title: string; range: TextRange; selection: Selection | null; chooseLine?: (unit: Unit) => void;
  navigateLine?: (event: KeyboardEvent<HTMLButtonElement>, index: number) => void;
  lineRefs?: React.MutableRefObject<Map<number, HTMLButtonElement>>;
}) {
  return <section className={styles.textColumn} lang={range.language === "grc" ? "grc" : "en"}><h3>{title}</h3><ol>
    {range.units.map((unit, index) => { const active = !!selection && unit.line_end >= selection.start && unit.line_start <= selection.end; return <li key={unit.text_unit_id} className={active ? styles.selectedLine : ""}>
      {chooseLine ? <button ref={(node) => { if (node) lineRefs?.current.set(unit.line_start, node); }} aria-pressed={active} aria-label={`Select ${unit.citation}: ${unit.text}`} onClick={() => chooseLine(unit)} onKeyDown={(event) => navigateLine?.(event, index)}>{unit.line_start}{unit.line_end === unit.line_start ? "" : `–${unit.line_end}`}</button> : <span aria-hidden="true">{unit.line_start}{unit.line_end === unit.line_start ? "" : `–${unit.line_end}`}</span>}
      <p>{unit.text}</p></li>; })}
  </ol></section>;
}

function Interlinear({ greek, translations, ...props }: { greek: TextRange; translations: TextRange[]; selection: Selection | null; chooseLine: (unit: Unit) => void; navigateLine: (event: KeyboardEvent<HTMLButtonElement>, index: number) => void; lineRefs: React.MutableRefObject<Map<number, HTMLButtonElement>> }) {
  return <section className={styles.interlinearList} aria-label="Interlinear range alignment"><h3>Range-aligned text</h3><ol>{greek.units.map((unit, index) => {
    const matches = translations.flatMap((range) => range.units.filter((target) => target.line_start <= unit.line_start && target.line_end >= unit.line_start).map((target) => ({ label: range.version_label, text: target.text })));
    const active = !!props.selection && unit.line_end >= props.selection.start && unit.line_start <= props.selection.end;
    return <li key={unit.text_unit_id} className={active ? styles.selectedLine : ""}><button ref={(node) => { if (node) props.lineRefs.current.set(unit.line_start, node); }} aria-pressed={active} onClick={() => props.chooseLine(unit)} onKeyDown={(event) => props.navigateLine(event, index)}>{unit.line_start}</button><div><p lang="grc">{unit.text}</p>{matches.map((match) => <p key={match.label}><small>{match.label}</small>{match.text}</p>)}</div></li>;
  })}</ol></section>;
}
