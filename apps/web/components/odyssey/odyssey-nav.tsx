"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

const BOOK_ONE_TEXT =
  "/sourcecut-api/api/v1/text/odyssey-perseus-grc2/1/parallel?from_line=1&to_line=80&targets=odyssey-perseus-eng3";
let bookOnePrefetch: Promise<void> | undefined;

function prefetchBookOne() {
  bookOnePrefetch ??= fetch(BOOK_ONE_TEXT)
    .then((response) => {
      if (!response.ok) throw new Error("Book I prefetch failed");
      return response.arrayBuffer();
    })
    .then(() => undefined)
    .catch(() => {
      bookOnePrefetch = undefined;
    });
}

const items = [
  { href: "/odyssey/read/1", label: "Read", match: "/odyssey/read" },
  { href: "/odyssey/search", label: "Search", match: "/odyssey/search" },
  { href: "/odyssey/timeline", label: "Timeline", match: "/odyssey/timeline" },
  { href: "/odyssey/voyage", label: "Voyage", match: "/odyssey/voyage" },
  { href: "/odyssey/entities", label: "Entities", match: "/odyssey/entities" },
  { href: "/odyssey/themes", label: "Themes", match: "/odyssey/themes" },
  {
    href: "/odyssey/visual-culture",
    label: "Visuals",
    match: "/odyssey/visual-culture",
  },
  { href: "/odyssey/claims", label: "Claims", match: "/odyssey/claims" },
  { href: "/odyssey/boards", label: "Boards", match: "/odyssey/boards" },
];

export default function OdysseyNav() {
  const pathname = usePathname();
  const activeRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    const active = activeRef.current;
    const nav = active?.parentElement;
    if (!active || !nav) return;
    nav.scrollTo({
      left: active.offsetLeft - (nav.clientWidth - active.clientWidth) / 2,
      behavior: "smooth",
    });
  }, [pathname]);

  useEffect(() => {
    if (pathname.startsWith("/odyssey/read")) return;
    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(prefetchBookOne, { timeout: 1_000 });
      return () => window.cancelIdleCallback(id);
    }
    const id = globalThis.setTimeout(prefetchBookOne, 200);
    return () => globalThis.clearTimeout(id);
  }, [pathname]);

  return (
    <nav aria-label="Odyssey research">
      {items.map((item) => {
        const active = pathname.startsWith(item.match);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={active ? styles.activeNav : undefined}
            href={item.href}
            key={item.href}
            onPointerEnter={item.href === "/odyssey/read/1" ? prefetchBookOne : undefined}
            ref={active ? activeRef : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
