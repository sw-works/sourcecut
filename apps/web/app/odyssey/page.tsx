import Link from "next/link";
import Image from "next/image";
import papyrus from "../../public/odyssey/media/248134.jpg";
import styles from "./odyssey.module.css";

const books = Array.from({ length: 24 }, (_, index) => index + 1);

export default function OdysseyHome() {
  return (
    <main id="odyssey-main">
      <section className={styles.odysseyHero}>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>Homer · Ὀδύσσεια</p>
          <h1>
            The poem,
            <br />
            line by line.
          </h1>
          <p className={styles.lede}>
            Read pinned Greek beside public translations, then trace every claim
            to its exact line.
          </p>
          <div className={styles.heroActions}>
            <Link className={styles.primaryLink} href="/odyssey/read/1">
              Open Book I <span>→</span>
            </Link>
            <Link className={styles.secondaryLink} href="/odyssey/search">
              Search the corpus
            </Link>
          </div>
        </div>
        <figure className={styles.heroArtifact}>
          <Image
            alt="Papyrus fragment preserving lines from Homer's Odyssey"
            fill
            priority
            sizes="(max-width: 800px) 100vw, 44vw"
            src={papyrus}
          />
          <figcaption>
            <span>Ancient witness</span>
            <strong>Odyssey papyrus, ca. 285–250 BCE</strong>
            <small>The Met · Public domain · Comparative source</small>
          </figcaption>
        </figure>
      </section>
      <nav className={styles.researchPaths} aria-label="Begin Odyssey research">
        <Link href="/odyssey/search">
          <span>01</span>
          <strong>Find a line</strong>
          <small>Word, lemma, phrase, or citation</small>
        </Link>
        <Link href="/odyssey/voyage">
          <span>02</span>
          <strong>Trace the voyage</strong>
          <small>Sequence and competing geographies</small>
        </Link>
        <Link href="/odyssey/visual-culture">
          <span>03</span>
          <strong>Inspect reception</strong>
          <small>Ancient objects and later images</small>
        </Link>
        <Link href="/odyssey/claims">
          <span>04</span>
          <strong>Test a claim</strong>
          <small>Evidence roles and publication boundary</small>
        </Link>
      </nav>
      <section className={styles.bookIndex} aria-labelledby="book-index-title">
        <div>
          <p className={styles.eyebrow}>Twenty-four books</p>
          <h2 id="book-index-title">Choose a book</h2>
          <p>
            The reader loads a bounded context window and never changes the
            cited span.
          </p>
        </div>
        <ol>
          {books.map((book) => (
            <li key={book}>
              <Link href={`/odyssey/read/${book}`}>
                <span>{String(book).padStart(2, "0")}</span>
                <strong>Book {roman(book)}</strong>
              </Link>
            </li>
          ))}
        </ol>
      </section>
      <section className={styles.provenanceBand}>
        <p className={styles.eyebrow}>The evidence contract</p>
        <div>
          <article>
            <span>01</span>
            <h3>Version identity</h3>
            <p>Greek and translations are always named independently.</p>
          </article>
          <article>
            <span>02</span>
            <h3>Stable citations</h3>
            <p>Human references and CTS URNs resolve to the same lines.</p>
          </article>
          <article>
            <span>03</span>
            <h3>Source custody</h3>
            <p>
              Raw TEI, upstream revision, and content hash remain traceable.
            </p>
          </article>
        </div>
      </section>
    </main>
  );
}

function roman(value: number): string {
  const numerals: [number, string][] = [
    [10, "X"],
    [9, "IX"],
    [5, "V"],
    [4, "IV"],
    [1, "I"],
  ];
  let remaining = value;
  let result = "";
  for (const [amount, numeral] of numerals) {
    while (remaining >= amount) {
      result += numeral;
      remaining -= amount;
    }
  }
  return result;
}
