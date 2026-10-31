import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router";
import { STATUS } from "../lib/text";
import type { Action } from "../api/types";

// ---- Button ----------------------------------------------------------------------------------------------
type Kind = "primary" | "secondary" | "ghost";
const KIND: Record<Kind, string> = {
  primary: "bg-accent text-accent-ink border-transparent hover:opacity-90",
  secondary: "bg-surface text-ink border-rule-strong hover:bg-sunken",
  ghost: "bg-transparent text-accent border-transparent hover:bg-sunken font-normal",
};
export function Button({ kind = "secondary", kbd, className = "", children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: Kind; kbd?: string }) {
  return (
    <button type="button" {...rest} className={`inline-flex h-10 items-center justify-center gap-2 rounded border px-4 font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${KIND[kind]} ${className}`}>
      {children}
      {kbd && <span className={`kbd ml-1 ${kind === "primary" ? "!border-accent-ink/40 !bg-transparent !text-accent-ink" : ""}`}>{kbd}</span>}
    </button>
  );
}

// ---- Status words: plain text, colour only for "must review" -------------------------------------------------
export function AlertDot() { return <span className="inline-block h-2 w-2 shrink-0 rounded-full bg-alert" aria-hidden />; }

export function Status({ action, severe }: { action: Action | null; severe?: boolean }) {
  if (!action) return null;
  const alert = action === "REVIEW_OBJECTION" || severe;
  return (
    <span className={`inline-flex items-center gap-1.5 text-meta ${alert ? "text-alert" : "text-ink-2"}`}>
      {alert && <AlertDot />}{STATUS[action]}
    </span>
  );
}

// ---- Strength: one number, one bar. Lines are labelled where the bar is large. ----------------------------------
export function Bar60({ score }: { score: number | null }) {
  if (score == null) return <span className="text-meta text-ink-2">not scored</span>;
  return (
    <span className="inline-flex items-center gap-3" role="img" aria-label={`Strength ${score} of 100`}>
      <span className="w-6 text-right font-semibold tnum">{score}</span>
      <span className="relative h-1.5 w-[60px] rounded-full bg-sunken"><span className="absolute inset-y-0 left-0 rounded-full bg-ink-2" style={{ width: `${score}%` }} /></span>
    </span>
  );
}

export function StrengthLine({ score, fund, park }: { score: number | null; fund: number; park: number }) {
  if (score == null) return null;
  return (
    <div className="mt-5 max-w-[560px]" role="img" aria-label={`Strength ${score} of 100. Park line ${park}, fund line ${fund}.`}>
      <div className="relative h-2 rounded-full bg-sunken">
        <div className="absolute inset-y-0 left-0 rounded-full bg-ink" style={{ width: `${score}%` }} />
        <div className="absolute -inset-y-1 w-px bg-ink-2" style={{ left: `${park}%` }} />
        <div className="absolute -inset-y-1 w-px bg-accent" style={{ left: `${fund}%` }} />
      </div>
      <div className="relative mt-1 h-5 text-meta tnum text-ink-2">
        <span className="absolute -translate-x-1/2" style={{ left: `${park}%` }}>Park {park}</span>
        <span className="absolute -translate-x-1/2 text-accent" style={{ left: `${fund}%` }}>Fund {fund}</span>
      </div>
    </div>
  );
}

// ---- Layout ----------------------------------------------------------------------------------------------
export function Page({ children, narrow }: { children: ReactNode; narrow?: boolean }) {
  return <div className={`mx-auto px-4 py-10 md:px-12 ${narrow ? "max-w-[1000px]" : "max-w-[1200px]"}`}>{children}</div>;
}
export function PageHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-display">{title}</h1>{sub && <p className="measure mt-1 text-ink-2">{sub}</p>}</div>
      {right}
    </div>
  );
}
export function Empty({ title, body, action }: { title: string; body?: string; action?: ReactNode }) {
  return <div className="py-12 text-center"><div className="serif text-lead">{title}</div>{body && <p className="mx-auto mt-1 max-w-md text-ink-2">{body}</p>}{action && <div className="mt-3">{action}</div>}</div>;
}
export function Loading({ rows = 4 }: { rows?: number }) {
  return <div className="space-y-2 py-4" aria-busy="true" aria-label="Loading">{Array.from({ length: rows }, (_, i) => <div key={i} className="h-12 animate-pulse rounded bg-sunken" />)}</div>;
}
export function ErrorNote({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="rounded border border-rule-strong p-4" role="alert">
      <p className="font-semibold">That did not load.</p>
      <p className="text-ink-2">{error instanceof Error ? error.message : "Something went wrong."}</p>
      {retry && <Button className="mt-3" onClick={retry}>Try again</Button>}
    </div>
  );
}
export function SectionTitle({ children, alert }: { children: ReactNode; alert?: boolean }) {
  return <h3 className={`mb-1 text-meta font-semibold ${alert ? "text-alert" : "text-ink-2"}`}>{children}</h3>;
}

export function Tabs<T extends string>({ items, active, onChange }: { items: { key: T; label: string; n?: number }[]; active: T; onChange: (k: T) => void }) {
  return (
    <div role="tablist" className="flex gap-1 overflow-x-auto border-b border-rule">
      {items.map((t) => (
        <button key={t.key} role="tab" aria-selected={t.key === active} onClick={() => onChange(t.key)}
          className={`-mb-px inline-flex h-11 items-center whitespace-nowrap border-b-2 px-3 ${t.key === active ? "border-ink font-semibold text-ink" : "border-transparent text-ink-2 hover:text-ink"}`}>
          {t.label}{t.n != null && <span className="ml-1.5 font-normal text-ink-2 tnum">{t.n}</span>}
        </button>
      ))}
    </div>
  );
}

export function IdeaLink({ id, children, className = "" }: { id: string; children: ReactNode; className?: string }) {
  return <Link to={`/ideas/${id}`} title={id} className={`hover:underline ${className}`}>{children}</Link>;
}

// ---- Dialog: focus trap, Esc, focus restored. A bottom sheet on a phone. ------------------------------------------
export function Dialog({ onClose, label, children, wide }: { onClose: () => void; label: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>("button, input, textarea, select, a[href]");
    first?.focus();
    return () => prev?.focus?.();
  }, []);
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); }
    if (e.key === "Tab" && ref.current) {
      const f = [...ref.current.querySelectorAll<HTMLElement>("button:not([disabled]), input, textarea, select, a[href]")];
      if (!f.length) return;
      const a = f[0], z = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    }
  };
  return createPortal(
    <>
      <div className="fixed inset-0 z-40 bg-ink/30" onClick={onClose} />
      <div ref={ref} role="dialog" aria-modal="true" aria-label={label} onKeyDown={onKey}
        className={`rise fixed inset-x-0 bottom-0 z-50 max-h-[88vh] overflow-y-auto rounded-t-lg border border-rule-strong bg-surface shadow-2xl md:inset-x-auto md:bottom-auto md:left-1/2 md:top-[8vh] md:-translate-x-1/2 md:rounded-lg ${wide ? "md:w-[min(760px,94vw)]" : "md:w-[min(640px,94vw)]"}`}>
        {children}
      </div>
    </>,
    document.body,
  );
}
