"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Slides its content in the first time it scrolls into view. The motion is plain CSS (see [data-reveal] in
 * globals.css), which only hides anything when scripts are on and the visitor has not asked for reduced
 * motion, so without JavaScript, or with reduced motion, the content is simply there.
 * Import it directly from this file, not through the ui index.
 */
export function Reveal({
  children,
  from = "up",
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  from?: "up" | "left" | "right";
  /** Milliseconds to wait, to stagger a row of cards. */
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        setShown(true);
        io.disconnect();
      },
      { threshold: 0.12, rootMargin: "0px 0px -6% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      data-reveal={from}
      data-shown={shown ? "" : undefined}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
      className={className}
    >
      {children}
    </div>
  );
}
