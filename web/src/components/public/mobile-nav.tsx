"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { isCurrentPath, type NavItem } from "./nav-links";

/**
 * The menu for narrow screens: one button that opens the whole list, children of "Who we are" included. It closes
 * on Escape (focus goes back to the button), on a tap outside, and when a link is followed.
 */
export function MobileNav({ items, overlay = false }: { items: NavItem[]; overlay?: boolean }) {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  // Close when the page changes (state adjusted while rendering, not in an effect).
  const [openedOn, setOpenedOn] = useState(pathname);
  if (openedOn !== pathname) {
    setOpenedOn(pathname);
    setOpen(false);
  }
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [open]);

  const row = "flex min-h-11 items-center rounded-xl px-3 text-body font-medium text-ink transition-colors hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ink aria-[current]:bg-sunken";

  return (
    <div
      ref={root}
      onKeyDown={(e) => {
        if (e.key === "Escape" && open) {
          setOpen(false);
          button.current?.focus();
        }
      }}
    >
      <button
        ref={button}
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={open ? "Close menu" : "Open menu"}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "inline-flex size-11 items-center justify-center rounded-full transition-[background-color,transform] duration-150 active:scale-[0.96] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-current motion-reduce:transition-none",
          overlay ? "bg-[rgb(20_14_8/0.62)] text-white backdrop-blur-md hover:bg-[rgb(20_14_8/0.8)]" : "text-ink hover:bg-sunken",
        )}
      >
        {open ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
      </button>
      {open && (
        <nav
          id={panelId}
          aria-label="Menu"
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("a")) setOpen(false); // also closes for links that stay on this page
          }}
          className="menu-pop absolute inset-x-3 top-full z-40 mt-1 max-h-[calc(100dvh-5rem)] overflow-y-auto rounded-card border border-line bg-surface p-2 text-ink shadow-lifted sm:inset-x-6"
        >
          <ul>
            {items.map((item) => (
              <li key={item.label}>
                {item.children ? (
                  <>
                    <p className="px-3 pb-1 pt-3 text-caption font-semibold uppercase tracking-widest text-faint">{item.label}</p>
                    <ul>
                      {item.children.map((c) => (
                        <li key={c.href}>
                          <Link href={c.href} aria-current={isCurrentPath(pathname, c.href) ? "page" : undefined} className={cn(row, "pl-6")}>{c.label}</Link>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <Link href={item.href} aria-current={isCurrentPath(pathname, item.href) ? "page" : undefined} className={row}>{item.label}</Link>
                )}
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
