import { useMemo, useState } from "react";
import { useNavigate } from "react-router";
import type { IdeaSummary } from "../api/types";
import { Dialog } from "../ui/primitives";

interface Cmd { group: string; label: string; sub?: string; run: () => void }
const fuzzy = (q: string, s: string) => { q = q.toLowerCase(); s = s.toLowerCase(); if (!q) return 1; if (s.includes(q)) return 100 - s.indexOf(q); let n = 0; for (const c of s) if (c === q[n]) n++; return n === q.length ? 10 : 0; };

export function CommandPalette({ ideas, onClose, toggleTheme }: { ideas: IdeaSummary[]; onClose: () => void; toggleTheme: () => void }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(0);
  const cmds = useMemo<Cmd[]>(() => [
    ...([["/today", "Today"], ["/ideas", "Ideas"], ["/log", "Log"], ["/team", "The team"], ["/how-it-works", "How it works"], ["/portfolio", "Portfolio balance"], ["/settings", "Settings and calibration"], ["/runs", "Pipeline runs"], ["/signals", "Signals"]] as const)
      .map(([to, l]) => ({ group: "Go to", label: l, run: () => nav(to) })),
    { group: "Actions", label: "Switch light or dark", run: toggleTheme },
    ...ideas.map((i) => ({ group: "Ideas", label: i.title, run: () => nav(`/ideas/${i.id}`) })),
  ], [ideas, nav, toggleTheme]);
  const shown = useMemo(() => cmds.map((c) => ({ c, s: fuzzy(q, c.label) })).filter((x) => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 12).map((x) => x.c), [cmds, q]);
  const run = (c?: Cmd) => { if (!c) return; onClose(); c.run(); };
  return (
    <Dialog onClose={onClose} label="Search or jump">
      <div onKeyDown={(e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(shown.length - 1, s + 1)); }
        if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
        if (e.key === "Enter") { e.preventDefault(); run(shown[sel]); }
      }}>
        <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setSel(0); }} placeholder="Search ideas, or jump to a page"
          className="h-14 w-full border-b border-rule bg-transparent px-6 outline-none placeholder:text-ink-2" aria-label="Search" />
        <ul className="max-h-[50vh] overflow-y-auto py-2" role="listbox">
          {shown.map((c, i) => (
            <li key={`${c.group}-${c.label}`} role="option" aria-selected={i === sel}>
              <button className={`flex w-full items-baseline gap-3 px-6 py-2 text-left ${i === sel ? "bg-sunken" : ""}`} onMouseEnter={() => setSel(i)} onClick={() => run(c)}>
                <span className="w-16 shrink-0 text-meta text-ink-2">{c.group}</span><span className="flex-1">{c.label}</span>
              </button>
            </li>
          ))}
          {!shown.length && <li className="px-6 py-4 text-ink-2">Nothing matches.</li>}
        </ul>
      </div>
    </Dialog>
  );
}
