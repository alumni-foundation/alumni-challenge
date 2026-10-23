"use client";

import { CheckCircle2, Info } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

type Toast = { id: number; message: string; tone: "ok" | "info" };
type Push = (message: string, tone?: Toast["tone"]) => void;

const ToastContext = createContext<Push>(() => {});
export const useToast = () => useContext(ToastContext);

/** Short confirmations ("Saved"). They sit above the phone tab bar and never steal focus. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(0);

  const push = useCallback<Push>((message, tone = "ok") => {
    const id = next.current++;
    setToasts((t) => [...t, { id, message, tone }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);
  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex flex-col items-center gap-2 px-4 lg:bottom-6"
      >
        {toasts.map((t) => {
          const Icon = t.tone === "ok" ? CheckCircle2 : Info;
          return (
            <div
              key={t.id}
              className={cn(
                "pointer-events-auto flex max-w-sm items-center gap-2.5 rounded-control border border-line-strong bg-surface px-4 py-3 text-small shadow-lifted motion-rise",
              )}
            >
              <Icon className={cn("size-4 shrink-0", t.tone === "ok" ? "text-ok" : "text-muted")} aria-hidden />
              {t.message}
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
