"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import styles from "../../app/odyssey/odyssey.module.css";

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
            ref={active ? activeRef : undefined}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
