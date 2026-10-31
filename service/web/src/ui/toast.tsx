import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

interface ToastItem { id: number; message: ReactNode; undo?: () => void; progressMs?: number; tone?: "error" }
interface ToastApi { show: (message: ReactNode, opts?: { undo?: () => void; ms?: number; tone?: "error" }) => () => void }
const Ctx = createContext<ToastApi>({ show: () => () => {} });
export const useToast = () => useContext(Ctx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const n = useRef(0);
  const dismiss = useCallback((id: number) => setItems((xs) => xs.filter((x) => x.id !== id)), []);
  const api = useMemo<ToastApi>(() => ({
    show: (message, opts) => {
      const id = ++n.current;
      const ms = opts?.ms ?? 4200;
      setItems((xs) => [...xs, { id, message, undo: opts?.undo, progressMs: opts?.undo ? ms : undefined, tone: opts?.tone }]);
      window.setTimeout(() => dismiss(id), ms + 200);
      return () => dismiss(id);
    },
  }), [dismiss]);
  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="fixed bottom-16 md:bottom-6 left-1/2 -translate-x-1/2 z-[60] flex w-[min(92vw,560px)] flex-col items-stretch gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="rise flex items-center gap-4 rounded-md border border-rule-strong bg-surface px-4 py-3 shadow-lg">
            <span className={`flex-1 ${t.tone === "error" ? "text-alert" : ""}`}>{t.message}</span>
            {t.undo && (
              <button onClick={() => { t.undo?.(); dismiss(t.id); }} className="h-10 px-3 font-semibold text-accent hover:underline">
                Undo <span className="kbd ml-1">z</span>
              </button>
            )}
            {t.progressMs && (
              <span className="h-1 w-12 overflow-hidden rounded-full bg-sunken" aria-hidden>
                <span className="block h-full bg-accent" style={{ width: "100%", animation: `shrink ${t.progressMs}ms linear forwards` }} />
              </span>
            )}
          </div>
        ))}
      </div>
      <style>{"@keyframes shrink { to { width: 0% } }"}</style>
    </Ctx.Provider>
  );
}
