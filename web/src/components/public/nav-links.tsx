"use client";

import { ChevronDown } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type NavChild = { href: string; label: string };
export type NavItem = {
  href: string;
  label: string;
  /** Set for the links that scroll within the landing page instead of going to another page. */
  section?: "home" | "schools" | "partners";
  /** A drop-down: the item itself is a button that opens these links. */
  children?: NavChild[];
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

/** True for the page the link points at, or any page beneath it ("/blog" is current on "/blog/some-post"). */
export const isCurrentPath = (pathname: string, href: string) => (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`));

/**
 * A drop-down that works three ways. Mouse: it opens when the pointer rests on it and closes when the pointer leaves.
 * Keyboard: Enter or Space (or the down arrow) opens it and moves into the list, Escape closes it and gives focus back
 * to the button, and tabbing out closes it. Touch: a tap opens it and a second tap, or a tap elsewhere, closes it.
 */
function Dropdown({ item, current, linkClassName }: { item: NavItem; current: boolean; linkClassName?: string }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const pathname = usePathname();
  const menuId = useId();
  const children = item.children ?? [];

  // Close when the page changes (state adjusted while rendering, not in an effect).
  const [openedOn, setOpenedOn] = useState(pathname);
  if (openedOn !== pathname) {
    setOpenedOn(pathname);
    setOpen(false);
  }
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const firstLink = () => wrap.current?.querySelector<HTMLAnchorElement>("a")?.focus();

  return (
    <div
      ref={wrap}
      className="relative"
      onPointerEnter={(e) => {
        if (e.pointerType !== "mouse") return;
        clearTimeout(timer.current);
        setOpen(true);
      }}
      onPointerLeave={(e) => {
        if (e.pointerType !== "mouse") return;
        timer.current = setTimeout(() => setOpen(false), 140);
      }}
      onBlur={(e) => {
        if (!wrap.current?.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          e.preventDefault();
          setOpen(false);
          button.current?.focus();
        }
      }}
    >
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={menuId}
        aria-current={current ? "page" : undefined}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            requestAnimationFrame(firstLink);
          }
        }}
        className={cn("nav-link", linkClassName)}
      >
        {item.label}
        <ChevronDown className={cn("ml-1 size-4 transition-transform duration-150 motion-reduce:transition-none", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <ul id={menuId} className="menu-pop absolute left-0 top-full z-30 mt-1 min-w-48 rounded-card border border-line bg-surface p-1.5 text-ink shadow-lifted">
          {children.map((c) => (
            <li key={c.href}>
              <Link
                href={c.href}
                aria-current={isCurrentPath(pathname, c.href) ? "page" : undefined}
                className="flex min-h-11 items-center rounded-xl px-3 text-small font-medium text-muted transition-colors hover:bg-sunken hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink aria-[current]:bg-sunken aria-[current]:text-ink"
              >
                {c.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * The header links. On the landing page (`landing`) Home, Schools and Partners scroll within the page;
 * everywhere they are real links (so they work without JavaScript and for crawlers), and a click is only
 * taken over when the target is on this page. Each link underlines on hover and focus (CSS, `.nav-link`)
 * and keeps the underline while it is the current page or section. Items with `children` open a drop-down.
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
        if (item.children) {
          return <Dropdown key={item.label} item={item} current={item.children.some((c) => isCurrentPath(pathname, c.href))} linkClassName={linkClassName} />;
        }
        const current = landing ? (item.section ? active === item.section : false) : isCurrentPath(pathname, item.href);
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
