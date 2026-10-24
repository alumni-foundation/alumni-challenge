"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export type NavItem = {
  href: string;
  label: string;
  /** Set for the links that scroll within the landing page instead of going to another page. */
  section?: "home" | "schools" | "partners";
};

type Section = "home" | "schools" | "partners";

/** Which landing section is under the middle of the screen. "home" until the schools section is reached. */
function useActiveSection(enabled: boolean): Section {
  const [active, setActive] = useState<Section>("home");
  useEffect(() => {
    if (!enabled) return;
    const targets = (["schools", "partners"] as const).map((id) => document.getElementById(id)).filter((el): el is HTMLElement => el !== null);
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(entry.target.id as Section);
          else setActive((cur) => (cur === entry.target.id ? "home" : cur));
        }
      },
      { rootMargin: "-40% 0px -50% 0px" },
    );
    targets.forEach((t) => io.observe(t));
    return () => io.disconnect();
  }, [enabled]);
  return active;
}

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Resolves once the page has stopped scrolling (a smooth scroll in flight, or none at all). */
function settled(): Promise<void> {
  return new Promise((resolve) => {
    const start = performance.now();
    let last = window.scrollY;
    let still = 0;
    const tick = () => {
      const y = window.scrollY;
      still = Math.abs(y - last) < 1 ? still + 1 : 0;
      last = y;
      const elapsed = performance.now() - start;
      if ((still >= 8 && elapsed > 80) || elapsed > 1500) resolve();
      else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
}

/**
 * The header links. On the landing page (`landing`) Home, Schools and Partners scroll within the page;
 * everywhere they are real links (so they work without JavaScript and for crawlers), and a click is only
 * taken over when the target is on this page. Each link underlines on hover and focus (CSS, `.nav-link`)
 * and keeps the underline while it is the current page or section.
 */
export function NavLinks({ items, landing = false, className, linkClassName }: {
  items: NavItem[]; landing?: boolean; className?: string; linkClassName?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const active = useActiveSection(landing);

  async function onClick(e: React.MouseEvent<HTMLAnchorElement>, item: NavItem) {
    if (!landing || !item.section) return;
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    const { section } = item;
    const target = section === "home" ? null : document.getElementById(section);
    if (section !== "home" && !target) {
      router.push(`/${section}`); // the section is not on the page: go to the full page instead
      return;
    }
    const reduce = prefersReducedMotion();
    if (section === "home") window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    else target?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    const hash = section === "home" ? "/" : `/#${section}`;
    if (window.location.pathname + window.location.hash !== hash) window.history.pushState(null, "", hash);
    if (!reduce) await settled();
    // Move focus to the heading so keyboard and screen-reader users land where the page now is.
    const heading = section === "home" ? document.querySelector("h1") : document.getElementById(`${section}-title`);
    if (heading instanceof HTMLElement) heading.focus({ preventScroll: true });
  }

  return (
    <nav aria-label="Main" className={className}>
      {items.map((item) => {
        const current = landing && item.section ? active === item.section : !landing && (pathname === item.href || pathname.startsWith(`${item.href}/`));
        return (
          <Link
            key={item.label}
            href={item.href}
            onClick={(e) => void onClick(e, item)}
            aria-current={current ? (landing ? "location" : "page") : undefined}
            className={cn("nav-link", linkClassName)}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
