import { useState } from "react";
import { Link } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { usePortfolio } from "../api/hooks";
import type { Cell } from "../api/types";
import { useActions } from "../components/Actions";
import { CELLS } from "../lib/text";
import { Button, ErrorNote, Loading, Page, PageHead } from "../ui/primitives";

const cells: Cell[] = ["core", "adjacent", "transformational"];
const clean = (s: string) => s.replace(/\s*\((SD|PF|CAP)-\d+\)/g, "");

type Item = { id: string; name: string; kind: string; ambition_cell: Cell };

/** One live item. "Retag" moves it to another cell in place; the reason is kept in the ledger's history. */
function ItemRow({ x }: { x: Item }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [cell, setCell] = useState<Cell>(x.ambition_cell);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [retiring, setRetiring] = useState(false);
  const refresh = () => { for (const k of ["portfolio", "board", "inbox"]) qc.invalidateQueries({ queryKey: [k] }); };
  const retire = async () => {
    setBusy(true); setErr(null);
    try { await api.post(`/api/portfolio/${x.id}/retirement`, { reason }); setOpen(false); setReason(""); refresh(); }
    catch (e) { setErr(e instanceof ApiError ? e.detail : "Could not retire it."); }
    finally { setBusy(false); }
  };
  const save = async () => {
    setBusy(true); setErr(null);
    try {
      await api.patch(`/api/portfolio/${x.id}`, { ambition_cell: cell, reason });
      setOpen(false); setReason(""); refresh();
    } catch (e) { setErr(e instanceof ApiError ? e.detail : "Could not save."); }
    finally { setBusy(false); }
  };
  return (
    <li title={x.id}>
      {clean(x.name)}{x.kind === "in_flight" && <span className="text-meta text-ink-2"> · in flight</span>}{x.kind === "future_goal" && <span className="text-meta text-ink-2"> · {CELLS[x.ambition_cell]} if pursued</span>}
      {!open && <button type="button" className="ml-2 text-meta text-accent hover:underline" onClick={() => { setRetiring(false); setOpen(true); }}>Retag</button>}
      {!open && <button type="button" className="ml-2 text-meta text-accent hover:underline" onClick={() => { setRetiring(true); setOpen(true); }}>Retire</button>}
      {open && (
        <div className="mt-2 mb-3 space-y-2 rounded border border-rule p-3">
          {retiring
            ? <p className="text-meta text-ink-2">Retire this item. It leaves the book and stops counting toward the mix. The history keeps it.</p>
            : <label className="block text-meta text-ink-2">Move to
              <select className="ml-2 rounded border border-rule bg-transparent px-2 py-1" value={cell} onChange={(e) => setCell(e.target.value as Cell)}>
                {cells.map((c) => <option key={c} value={c}>{CELLS[c]}</option>)}
              </select>
            </label>}
          <label className="block text-meta text-ink-2">Why
            <input className="mt-1 block w-full rounded border border-rule bg-transparent px-2 py-1" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="One line, for the record" />
          </label>
          {err && <p className="text-meta text-alert">{err}</p>}
          <div className="flex gap-2">
            <Button kind="primary" disabled={busy || (!retiring && cell === x.ambition_cell) || reason.trim().length < 10} onClick={retiring ? retire : save}>{retiring ? "Retire" : "Save"}</Button>
            <Button onClick={() => { setOpen(false); setCell(x.ambition_cell); setErr(null); }}>Cancel</Button>
          </div>
        </div>
      )}
    </li>
  );
}

/** Adds a live item to one cell of the book. */
function AddItem({ cell }: { cell: Cell }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState<"line" | "in_flight" | "future_goal">("line");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const save = async () => {
    setBusy(true); setErr(null);
    try {
      await api.post("/api/portfolio", { kind, name: name.trim(), ambition_cell: cell });
      setOpen(false); setName("");
      for (const k of ["portfolio", "board", "inbox"]) qc.invalidateQueries({ queryKey: [k] });
    } catch (e) { setErr(e instanceof ApiError ? e.detail : "Could not add it."); }
    finally { setBusy(false); }
  };
  if (!open) return <button type="button" className="mb-4 text-meta text-accent hover:underline" onClick={() => setOpen(true)}>Add an item</button>;
  return (
    <div className="mb-4 space-y-2 rounded border border-rule p-3">
      <label className="block text-meta text-ink-2">Name
        <input className="mt-1 block w-full rounded border border-rule bg-transparent px-2 py-1" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label className="block text-meta text-ink-2">It is
        <select className="ml-2 rounded border border-rule bg-transparent px-2 py-1" value={kind} onChange={(e) => setKind(e.target.value as "line" | "in_flight" | "future_goal")}>
          <option value="line">A line we sell today</option>
          <option value="in_flight">Work in flight</option>
          <option value="future_goal">A future goal we are considering</option>
        </select>
      </label>
      {err && <p className="text-meta text-alert">{err}</p>}
      <div className="flex gap-2">
        <Button kind="primary" disabled={busy || name.trim().length < 3} onClick={save}>Add</Button>
        <Button onClick={() => { setOpen(false); setErr(null); }}>Cancel</Button>
      </div>
    </div>
  );
}

export default function Portfolio() {
  const q = usePortfolio();
  const actions = useActions();
  if (q.isLoading) return <Page><Loading rows={6} /></Page>;
  if (q.error) return <Page><ErrorNote error={q.error} retry={() => q.refetch()} /></Page>;
  const p = q.data!;
  const tol = p.target.tolerance ?? 0.05;
  const total = cells.reduce((n, c) => n + p.counts[c], 0);
  const bold = p.candidates.transformational[0] ?? p.parked_bold[0];
  return (
    <Page>
      <PageHead title="Portfolio" sub={p.in_band ? "The book is in balance." : `Out of balance. ${p.alarms[0] ? p.alarms[0][0].toUpperCase() + p.alarms[0].slice(1) + "." : ""}`} />
      <section className="mb-14">
        <h2 className="mb-1 text-meta font-semibold text-ink-2" style={{ fontFamily: "var(--font-sans)" }}>Mix against your aim</h2>
        <ul className="max-w-[900px]">
          {cells.map((c) => {
            const s = p.shares[c], t = p.target[c], out = Math.abs(s - t) > tol;
            return (
              <li key={c} className="grid grid-cols-[150px_1fr_220px] items-center gap-6 border-t border-rule py-3">
                <span>{CELLS[c]}</span>
                <div className="relative h-2 rounded-full bg-sunken" role="img" aria-label={`${CELLS[c]} ${Math.round(s * 100)} percent, aim ${Math.round(t * 100)} percent`}>
                  <div className={`absolute inset-y-0 left-0 rounded-full ${out ? "bg-ink" : "bg-ink-2"}`} style={{ width: `${Math.max(1, s * 100)}%` }} />
                  <div className="absolute -inset-y-1.5 w-0.5 bg-accent" style={{ left: `${t * 100}%` }} />
                </div>
                <span className="tnum"><b className="font-semibold">{Math.round(s * 100)}%</b> <span className="text-ink-2">against an aim of {Math.round(t * 100)}%</span>{out && <span className={`block text-meta ${c === "transformational" ? "text-alert" : "text-ink-2"}`}>{s > t ? "too much" : "too little"}</span>}</span>
              </li>
            );
          })}
        </ul>
        <p className="mt-2 text-meta text-ink-2">The blue mark is the aim. Within {Math.round(tol * 100)} points of it counts as in range. {total} live items.</p>
      </section>
      <section className="mb-14 max-w-[760px]">
        <h2 className="mb-1 text-meta font-semibold text-alert" style={{ fontFamily: "var(--font-sans)" }}>Bold bets: {p.counts.transformational} of {p.floor ?? 0} seats filled</h2>
        {bold ? <p className="serif text-lead">{p.candidates.transformational.length ? "The strongest bold idea is" : "The only bold idea,"} <Link to={`/ideas/${bold.id}`} className="text-accent hover:underline">{bold.title}</Link>{p.candidates.transformational.length ? "." : ", is parked."}</p> : <p className="serif text-lead">No bold idea is on the board.</p>}
        <div className="mt-4 flex flex-wrap gap-2">{bold && !p.candidates.transformational.length && <Button kind="primary" onClick={() => actions.decide(bold, "need_evidence")}>Put it back on the table</Button>}</div>
      </section>
      <section className="mb-14">
        <h2 className="mb-4 text-meta font-semibold text-ink-2" style={{ fontFamily: "var(--font-sans)" }}>Where the book and the board sit</h2>
        <div className="grid gap-10 md:grid-cols-3">
          {cells.map((c) => (
            <section key={c}><h3 className="serif mb-3 text-lead">{CELLS[c]}</h3>
              <ul className="mb-4 space-y-1.5">{p.items[c].map((x) => <ItemRow key={x.id} x={x} />)}{!p.items[c].length && <li className="text-ink-2">Nothing live here.</li>}</ul>
              <AddItem cell={c} />
              <p className="text-meta text-ink-2">{p.candidates[c].length ? <>{p.candidates[c].length} candidate{p.candidates[c].length === 1 ? "" : "s"} on the board. Strongest: <Link to={`/ideas/${p.candidates[c][0].id}`} className="text-accent hover:underline">{p.candidates[c][0].title}</Link> ({p.candidates[c][0].score}).</> : "No candidates on the board."}</p></section>
          ))}
        </div>
      </section>
      <section className="mb-14 max-w-[760px]">
        <h2 className="mb-1 text-meta font-semibold text-ink-2" style={{ fontFamily: "var(--font-sans)" }}>Areas of interest</h2>
        <p className="mb-3 text-meta text-ink-2">Goals we are considering and have not funded. They do not count in the mix above. The cell is where each would sit if we pursued it.</p>
        <ul className="space-y-1.5">
          {p.goals.map((x) => <ItemRow key={x.id} x={x} />)}
          {!p.goals.length && <li className="text-ink-2">No future goals yet. Add one from any cell above and choose "A future goal".</li>}
        </ul>
      </section>
      <section className="max-w-[900px]">
        <h2 className="mb-1 text-meta font-semibold text-ink-2" style={{ fontFamily: "var(--font-sans)" }}>Live work the candidates would crowd</h2>
        <ul>{p.overlaps.map((o) => {
          const avg = Math.round(o.ideas.reduce((n, x) => n + (x.cannibalization ?? 0), 0) / o.ideas.length);
          return <li key={o.item.id} className="border-t border-rule py-4" title={o.item.id}><div>{clean(o.item.name)} <span className="text-ink-2">· {o.ideas.length} candidate{o.ideas.length === 1 ? "" : "s"} overlap{o.ideas.length >= 4 ? ", crowded" : ""}</span></div>
            <p className="mt-1 text-meta text-ink-2">{o.ideas.map((x, i) => <span key={x.idea.id}>{i ? ", " : ""}<Link className="hover:underline" to={`/ideas/${x.idea.id}`}>{x.idea.title}</Link></span>)}. Average risk of taking business from it: {avg} of 100.</p></li>;
        })}</ul>
      </section>
    </Page>
  );
}
