import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./odyssey.module.css";
import "maplibre-gl/dist/maplibre-gl.css";

export default function OdysseyLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#odyssey-main">Skip to text</a>
      <header className={styles.masthead}>
        <Link className={styles.wordmark} href="/odyssey">SourceCut <span>/ Odyssey</span></Link>
        <nav aria-label="Odyssey research">
          <Link href="/odyssey/read/1">Read</Link>
          <Link href="/odyssey/search">Search</Link>
          <Link href="/odyssey/timeline">Timeline</Link>
          <Link href="/odyssey/voyage">Voyage</Link>
          <Link href="/odyssey/entities">Entities</Link>
          <Link href="/odyssey/themes">Themes</Link>
          <Link href="/odyssey/claims">Claims</Link>
        </nav>
        <p>Public citation preview</p>
      </header>
      {children}
    </div>
  );
}
