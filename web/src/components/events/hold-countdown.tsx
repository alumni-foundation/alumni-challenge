"use client";

import { Hourglass } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { timeLeft, timeText } from "@/lib/events";

/**
 * "Seats held until 18:42, 12:05 left". It counts down every second and, when the time is up, calls `onExpire`
 * once so the page can ask the server what happened to the booking.
 */
export function HoldCountdown({ until, onExpire }: { until: string; onExpire?: () => void }) {
  const [now, setNow] = useState(() => Date.now());
  const fired = useRef(false);
  const left = timeLeft(until, now);

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);
  useEffect(() => {
    if (!left && !fired.current) {
      fired.current = true;
      onExpire?.();
    }
  }, [left, onExpire]);

  if (!left) return <p className="text-body font-semibold text-ink">The hold has ended. The places are released shortly, and this booking will show as expired.</p>;
  const mm = String(left.minutes).padStart(2, "0");
  const ss = String(left.seconds).padStart(2, "0");
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <p className="text-body text-ink">Seats held until <strong className="font-semibold">{timeText(until)}</strong></p>
      <p role="timer" aria-label={`${left.minutes} minutes ${left.seconds} seconds left`} className="inline-flex items-center gap-2 rounded-full bg-warn-soft px-3.5 py-1.5 font-semibold tabular-nums text-warn">
        <Hourglass className="size-4" aria-hidden /> {mm}:{ss} left
      </p>
    </div>
  );
}
