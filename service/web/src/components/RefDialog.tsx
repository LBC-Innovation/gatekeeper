import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { useRefCard } from "../api/hooks";
import { Button, Dialog, Loading } from "../ui/primitives";

const RefCtx = createContext<(code: string) => void>(() => {});
export const useOpenRef = () => useContext(RefCtx);

/** Mounted once. Any ID code in prose opens here, over the page you are on. Related codes inside the card swap the card, and Back returns. */
export function RefProvider({ children }: { children: ReactNode }) {
  const [stack, setStack] = useState<string[]>([]);
  const open = useCallback((code: string) => setStack([code]), []);
  const code = stack[stack.length - 1] ?? null;
  return (
    <RefCtx.Provider value={open}>
      {children}
      {code && <RefCard code={code} canBack={stack.length > 1} onBack={() => setStack((s) => s.slice(0, -1))}
        onOpen={(c) => setStack((s) => [...s, c])} onClose={() => setStack([])} />}
    </RefCtx.Provider>
  );
}

function RefCard({ code, canBack, onBack, onOpen, onClose }: { code: string; canBack: boolean; onBack: () => void; onOpen: (c: string) => void; onClose: () => void }) {
  const q = useRefCard(code);
  const nav = useNavigate();
  const c = q.data;
  return (
    <Dialog onClose={onClose} label={c ? `${c.label} ${c.code}` : code}>
      <div className="flex items-start gap-3 border-b border-rule p-5">
        <div className="min-w-0 flex-1">
          <p className="text-meta text-ink-2">{c?.label ?? "Looking up"} <span className="font-mono">{code}</span></p>
          <h2 className="mt-1 text-title leading-snug">{c?.title ?? (q.isError ? "Not found" : "…")}</h2>
        </div>
        <button onClick={onClose} aria-label="Close" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded text-ink-2 hover:bg-sunken hover:text-ink">✕</button>
      </div>
      <div className="max-h-[60vh] overflow-y-auto p-5">
        {q.isLoading && <Loading rows={3} />}
        {q.isError && <p className="text-ink-2">Nothing is filed under {code}. It may have been written by an agent as an example.</p>}
        {c?.lede && <p className="serif measure text-lead">{c.lede}</p>}
        {c && c.facts.length > 0 && (
          <dl className={`grid gap-x-4 gap-y-2 text-[15px] md:grid-cols-[130px_1fr] ${c.lede ? "mt-5" : ""}`}>
            {c.facts.map(([k, v]) => (<div key={k} className="contents"><dt className="text-ink-2">{k}</dt><dd className="min-w-0 break-words">{v}</dd></div>))}
          </dl>
        )}
        {c && c.related.length > 0 && (
          <div className="mt-6">
            <h3 className="mb-2 text-meta font-semibold text-ink-2">Connected</h3>
            <ul className="divide-y divide-rule border-y border-rule">
              {c.related.map((r) => (
                <li key={r.code}><button onClick={() => onOpen(r.code)} className="flex w-full items-baseline gap-3 py-2 text-left hover:text-accent">
                  <span className="w-[130px] shrink-0 font-mono text-[13px] text-ink-2">{r.code}</span><span className="min-w-0">{r.title}</span></button></li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 border-t border-rule px-5 py-3">
        {canBack && <Button kind="ghost" onClick={onBack}>Back</Button>}
        <span className="flex-1" />
        {c?.href && <Button onClick={() => { onClose(); nav(c.href!); }}>Open full record</Button>}
        <Button kind="ghost" onClick={onClose}>Close</Button>
      </div>
    </Dialog>
  );
}
