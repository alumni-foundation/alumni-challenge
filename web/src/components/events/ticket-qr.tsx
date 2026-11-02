"use client";

import { Copy } from "lucide-react";
import { useMemo, useState } from "react";
import { encode } from "uqr";
import { Button, useToast } from "@/components/ui";

const QUIET = 4; // the blank border a scanner needs, in modules

/** The dark modules as one SVG path: a run of neighbours in a row becomes one rectangle. */
function pathFor(rows: boolean[][]): string {
  const parts: string[] = [];
  rows.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      if (!row[x]) { x += 1; continue; }
      let end = x;
      while (end < row.length && row[end]) end += 1;
      parts.push(`M${x + QUIET} ${y + QUIET}h${end - x}v1h${-(end - x)}z`);
      x = end;
    }
  });
  return parts.join("");
}

/**
 * The ticket's QR code, drawn here in the browser from the ticket code: nothing is fetched, and the code is
 * never written anywhere but into the picture. Pure black on pure white, with its quiet border, so it scans at any
 * brightness. "Copy code" is the fallback for a scanner that cannot read the screen.
 */
export function TicketQr({ code, active }: { code: string; active: boolean }) {
  const toast = useToast();
  const [manual, setManual] = useState(false);
  const qr = useMemo(() => encode(code, { ecc: "M" }), [code]);
  const size = qr.size + QUIET * 2;

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      toast("Code copied.");
    } catch {
      setManual(true);
      toast("Couldn’t copy by itself. Select the code below and copy it.", "info");
    }
  }

  return (
    <div className="flex flex-col items-center gap-4">
      <div className={active ? "rounded-3xl border border-line bg-white p-3 shadow-raised" : "rounded-3xl border border-line bg-white p-3 opacity-40"}>
        <svg
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={active ? "QR code for this ticket. Show it at the entrance." : "QR code for this ticket. This ticket can no longer be used."}
          shapeRendering="crispEdges"
          className="block size-[min(78vw,20rem)]"
        >
          <rect width={size} height={size} fill="#ffffff" />
          <path d={pathFor(qr.data)} fill="#000000" />
        </svg>
      </div>
      <p className="max-w-xs text-center text-small text-ink">{active ? "Turn your screen brightness up when you scan." : "This ticket is not valid, so the code will not scan."}</p>
      <Button variant="secondary" size="sm" onClick={copy}><Copy className="size-4" aria-hidden /> Copy code</Button>
      {manual && (
        <input
          readOnly
          aria-label="Ticket code"
          value={code}
          onFocus={(e) => e.currentTarget.select()}
          className="w-full max-w-xs rounded-control border border-line-strong bg-surface px-3 py-2 font-mono text-caption text-ink"
        />
      )}
    </div>
  );
}
