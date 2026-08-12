import Link from "next/link";
import type { ReactNode } from "react";
import OdysseyNav from "../../components/odyssey/odyssey-nav";
import styles from "./odyssey.module.css";
import "maplibre-gl/dist/maplibre-gl.css";

export default function OdysseyLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <div className={styles.shell}>
      <a className={styles.skipLink} href="#odyssey-main">
        Skip to text
      </a>
      <header className={styles.masthead}>
        <Link className={styles.wordmark} href="/odyssey">
          <span>SourceCut</span>
          <strong>Odyssey</strong>
        </Link>
        <OdysseyNav />
        <p>
          <i aria-hidden="true" /> Public citation edition
        </p>
      </header>
      {children}
    </div>
  );
}
