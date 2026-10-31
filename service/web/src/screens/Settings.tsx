import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { useBoard, useConfig, useProposals } from "../api/hooks";
import type { WhatIf } from "../api/types";
import { Bar60, Button, ErrorNote, Loading, Page, PageHead, Tabs } from "../ui/primitives";
import { useToast } from "../ui/toast";

type Tab = "weights" | "taste" | "rules";
const SENSORS: Record<string, string> = { unexpected_occurrences: "Unexpected occurrences", incongruities: "Incongruities", process_needs: "Process needs", industry_market_change: "Industry and market change", demographics: "Demographics", perception_shifts: "Perception shifts", new_knowledge: "New knowledge" };
const SLIDERS = [["analyst", "Strategy", "How well it fits the strategy and what we can build."], ["steward", "Portfolio", "What it does to the balance of the book."], ["redteam_band", "Objections", "How far an open objection can pull strength down."]] as const;

function useSave() {
  const toast = useToast();
  const qc = useQueryClient();
  return async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); toast.show(ok); for (const k of ["config", "log", "board", "proposals"]) qc.invalidateQueries({ queryKey: [k] }); return true; }
    catch (e) { toast.show(e instanceof ApiError ? e.detail : "That could not be saved.", { tone: "error", ms: 8000 }); return false; }
  };
}

function Weights() {
  const cfg = useConfig();
  const board = useBoard();
  const props = useProposals();
  const save = useSave();
  const [w, setW] = useState<Record<string, number> | null>(null);
  const [reason, setReason] = useState("");
  const [debounced, setDebounced] = useState<Record<string, number> | null>(null);
  useEffect(() => { if (cfg.data && !w) setW(cfg.data.weights); }, [cfg.data, w]);
  useEffect(() => { const t = setTimeout(() => setDebounced(w), 250); return () => clearTimeout(t); }, [w]);
  const base = useQuery({ queryKey: ["whatif", "now", cfg.data?.weights], enabled: !!cfg.data, queryFn: () => api.post<WhatIf>("/api/what-if/weights", { weights: cfg.data!.weights }) });
  const next = useQuery({ queryKey: ["whatif", debounced], enabled: !!debounced, queryFn: () => api.post<WhatIf>("/api/what-if/weights", { weights: debounced }) });
  const titles = useMemo(() => Object.fromEntries((board.data?.rows ?? []).map((r) => [r.id, r.title])), [board.data]);
  if (cfg.isLoading || !w) return <Loading rows={6} />;
  if (cfg.error) return <ErrorNote error={cfg.error} />;
  const cur = cfg.data!.weights;
  const changed = SLIDERS.some(([k]) => w[k] !== cur[k]);
  const pos = (x?: WhatIf) => Object.fromEntries([...(x?.live_board ?? [])].sort((a, b) => b.score - a.score).map((r, n) => [r.idea_id, n + 1]));
  const was = pos(base.data), now = pos(next.data ?? base.data);
  const order = Object.keys(now).sort((a, b) => now[a] - now[b]);
  const moved = order.filter((id) => was[id] !== now[id]).length;
  const ag = (x?: WhatIf) => x ? `${Math.round((x.exemplar_agreement.agreement ?? 0) * x.exemplar_agreement.pairs)} of ${x.exemplar_agreement.pairs}` : "";
  const open = props.data?.open ?? [];
  return (
    <>
      <div className="grid gap-10 lg:grid-cols-[340px_1fr] lg:gap-14">
        <div className="space-y-6">
          {SLIDERS.map(([k, label, desc]) => (
            <div key={k}><div className="flex items-baseline justify-between"><label htmlFor={`w-${k}`} className="font-semibold">{label}</label><span className="tnum">{Math.round(w[k] * 100)}{w[k] !== cur[k] && <span className="ml-1 text-meta text-ink-2">(was {Math.round(cur[k] * 100)})</span>}</span></div>
              <input id={`w-${k}`} type="range" min={0} max={0.8} step={0.05} value={w[k]} onChange={(e) => setW({ ...w, [k]: Number(e.target.value) })} className="mt-2 w-full accent-[var(--accent)]" />
              <p className="text-meta text-ink-2">{desc}</p></div>
          ))}
          <p className="text-ink-2">{ag(next.data ?? base.data)} past calls ordered correctly{changed && base.data ? ` (now ${ag(base.data)})` : ""}.</p>
          <label className="block"><span className="text-meta text-ink-2">Why? Required to save.</span><input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="In your words" className="mt-1 h-10 w-full rounded border border-rule-strong bg-surface px-3 outline-none focus:border-accent" /></label>
          <div className="flex gap-2"><Button kind="primary" disabled={!changed || reason.trim().split(/\s+/).length < 3} onClick={async () => { if (await save(() => api.put("/api/config/weights", { weights: w, reason: reason.trim() }), "Weights saved. The board re-ranks at the next run.")) setReason(""); }}>Save weights</Button><Button kind="ghost" onClick={() => setW(cur)}>Reset</Button></div>
        </div>
        <div>
          <h3 className="mb-1 text-meta font-semibold text-ink-2">What would change: {moved ? `${moved} ideas move` : "nothing yet"}</h3>
          <ol>{order.map((id) => { const d = was[id] - now[id]; return (
            <li key={id} className={`grid grid-cols-[40px_1fr_120px_80px] items-center gap-4 border-t border-rule py-2 ${d ? "" : "text-ink-2"}`}><span className="tnum">{now[id]}</span><Link to={`/ideas/${id}`} className="truncate hover:underline">{titles[id] ?? id}</Link>
              <Bar60 score={Math.round((next.data ?? base.data)!.live_board.find((r) => r.idea_id === id)!.score * 100)} /><span className="text-right text-meta tnum">{d ? `${d > 0 ? "up" : "down"} ${Math.abs(d)}` : ""}</span></li>); })}</ol>
        </div>
      </div>
      <div className="mt-16 max-w-[760px] border-t border-rule pt-8">
        <h3 className="mb-2 text-meta font-semibold text-ink-2">Suggested changes from the Calibrator</h3>
        {open.length === 0 ? <p className="text-ink-2">None yet. The Calibrator compares your decisions with the panel's advice each week and suggests changes here when it finds a pattern.</p> : open.map((p) => <Proposal key={p.id} p={p} />)}
      </div>
    </>
  );
}

function Proposal({ p }: { p: { id: number; kind: string; rationale: string } }) {
  const save = useSave();
  const [reason, setReason] = useState("");
  return (
    <div className="mb-6"><p className="serif text-lead">{p.rationale}</p><p className="text-meta text-ink-2">A change to {p.kind}.</p>
      <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why? Required" className="mt-3 h-10 w-full rounded border border-rule-strong bg-surface px-3 outline-none focus:border-accent" />
      <div className="mt-2 flex gap-2"><Button kind="primary" disabled={reason.trim().split(/\s+/).length < 3} onClick={() => save(() => api.post(`/api/proposals/${p.id}/decision`, { accept: true, reason }), "Applied.")}>Apply</Button>
        <Button disabled={reason.trim().split(/\s+/).length < 3} onClick={() => save(() => api.post(`/api/proposals/${p.id}/decision`, { accept: false, reason }), "Not now. Recorded with your reason.")}>Not now</Button></div></div>
  );
}

function Taste() {
  const cfg = useConfig();
  const save = useSave();
  const [add, setAdd] = useState<Record<string, string>>({});
  if (cfg.isLoading) return <Loading />;
  if (cfg.error) return <ErrorNote error={cfg.error} />;
  const c = cfg.data!;
  const putTaste = (kind: "likes" | "dislikes", items: { text: string; supported_by: string[] }[], why: string) =>
    save(() => api.put("/api/config/taste", { taste: { ...c.taste, [kind]: items }, reason: why }), "Saved.");
  const putWatch = (wl: Record<string, string[]>, why: string) => save(() => api.put("/api/config/watchlist", { watchlist: wl, reason: why }), "Saved.");
  const list = (kind: "likes" | "dislikes") => (
    <section key={kind}><h3 className="serif mb-2 text-lead">{kind === "likes" ? "You like" : "You dislike"}</h3>
      <ul>{c.taste[kind].map((x, n) => <li key={x.text} className="flex items-start gap-3 border-t border-rule py-3"><span className="flex-1">{x.text}{x.supported_by.length > 0 && <span className="block text-meta text-ink-2">Learned from {x.supported_by.length} past call{x.supported_by.length === 1 ? "" : "s"}</span>}</span>
        <button aria-label={`Remove: ${x.text}`} className="inline-flex h-8 w-8 items-center justify-center rounded text-ink-2 hover:bg-sunken hover:text-alert" onClick={() => putTaste(kind, c.taste[kind].filter((_, i) => i !== n), `Removed: ${x.text}`)}>✕</button></li>)}</ul>
      <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); const t = (add[kind] ?? "").trim(); if (t) { void putTaste(kind, [...c.taste[kind], { text: t, supported_by: [] }], `Added: ${t}`); setAdd({ ...add, [kind]: "" }); } }}>
        <input value={add[kind] ?? ""} onChange={(e) => setAdd({ ...add, [kind]: e.target.value })} placeholder={`Add a ${kind === "likes" ? "like" : "dislike"}`} className="h-10 flex-1 rounded border border-rule-strong bg-surface px-3 outline-none focus:border-accent" /><Button>Add</Button></form></section>
  );
  const empty = Object.keys(SENSORS).filter((a) => !(c.watchlist[a] ?? []).length).length;
  return (
    <>
      <div className="grid gap-10 md:grid-cols-2">{list("likes")}{list("dislikes")}</div>
      <p className="mt-4 text-meta text-ink-2">The reason choices in the decision sheet come from these lines.</p>
      <section className="mt-16"><h3 className="serif mb-1 text-lead">Where the scouts look</h3>
        {empty > 0 && <p className="mb-3 text-ink-2">{empty} areas have no search terms, so nothing there is ever found. That is the likeliest reason no bold idea appears.</p>}
        <ul className="max-w-[900px]">{Object.keys(SENSORS).map((a) => { const terms = c.watchlist[a] ?? []; return (
          <li key={a} className="border-t border-rule py-4"><div className="flex items-baseline justify-between"><span className="font-semibold">{SENSORS[a]}</span><span className={`text-meta ${terms.length ? "text-ink-2" : "text-alert"}`}>{terms.length ? `${terms.length} search terms` : "Not searched"}</span></div>
            <p className="mt-1 text-ink-2">{terms.map((t, n) => <span key={t} className="whitespace-nowrap">{n ? ", " : ""}{t}<button aria-label={`Remove ${t}`} className="ml-1 text-ink-2 hover:text-alert" onClick={() => putWatch({ ...c.watchlist, [a]: terms.filter((x) => x !== t) }, `Removed term from ${SENSORS[a]}: ${t}`)}>✕</button></span>)}</p>
            <form className="mt-2 flex max-w-md gap-2" onSubmit={(e) => { e.preventDefault(); const t = (add[a] ?? "").trim(); if (t) { void putWatch({ ...c.watchlist, [a]: [...terms, t] }, `Added term to ${SENSORS[a]}: ${t}`); setAdd({ ...add, [a]: "" }); } }}>
              <input value={add[a] ?? ""} onChange={(e) => setAdd({ ...add, [a]: e.target.value })} placeholder="Add a search term" className="h-9 flex-1 rounded border border-rule-strong bg-surface px-3 outline-none focus:border-accent" /><Button>Add</Button></form></li>); })}</ul></section>
    </>
  );
}

function Rules() {
  const cfg = useConfig();
  if (cfg.isLoading) return <Loading />;
  if (cfg.error) return <ErrorNote error={cfg.error} />;
  const c = cfg.data!;
  const r = c.rules;
  const rows: [string, string | number, string][] = [
    ["Fund line", Math.round(r.promote * 100), "Strength at or above this: the panel suggests funding the check"], ["Park line", Math.round(r.park_below * 100), "Strength below this: the panel suggests parking"],
    ["Must review", Math.round(r.must_review_severity * 100), "An objection this serious always reaches you, even when the queue is full"], ["Default after", `${r.default_days} days`, "How long an undecided item waits before it takes its default"],
    ["Queue size", r.queue_size, "Decisions in front of you at once, besides serious objections"], ["Panel size", r.panel_per_run, "Ideas the full panel reviews in one run"],
  ];
  return (
    <div className="max-w-[760px]">
      <section><h3 className="serif mb-2 text-lead">Rules</h3><ul>{rows.map(([l, v, d]) => <li key={l} className="grid grid-cols-[140px_80px_1fr] gap-4 border-t border-rule py-3"><span className="font-semibold">{l}</span><span className="tnum">{v}</span><span className="text-ink-2">{d}</span></li>)}</ul></section>
      <section className="mt-12"><h3 className="serif mb-2 text-lead">Strategy</h3><ul>{c.directives.filter((d) => !d.retired).map((d) => <li key={d.id} className="border-t border-rule py-3" title={d.id}>{d.statement}{d.funded && <span className="text-meta text-ink-2"> · funded</span>}</li>)}</ul></section>
      <section className="mt-12"><h3 className="serif mb-2 text-lead">What we can build</h3><ul>{c.capabilities.map((x) => <li key={x.id} className="flex gap-4 border-t border-rule py-3" title={x.id}><span className="flex-1">{x.name}</span><span className="text-meta text-ink-2">{x.maturity === "production" ? "in production" : x.maturity}</span></li>)}</ul></section>
      <section className="mt-12"><h3 className="serif mb-2 text-lead">Off limits</h3>{c.exclusions.map((x) => <p key={x} className="text-ink-2">{x}</p>)}</section>
      <section className="mt-12 border-t border-rule pt-8"><p className="text-ink-2">These change what every reviewer reads, so they are edited with Claude: it drafts the change, shows what would move, and saves it here with your reason.</p></section>
    </div>
  );
}

export default function Settings() {
  const { tab = "weights" } = useParams();
  const nav = useNavigate();
  const t: Tab = (["weights", "taste", "rules"].includes(tab) ? tab : "weights") as Tab;
  return (
    <Page>
      <PageHead title="Settings" sub="Small changes happen here, each with a reason. Bigger ones are drafted with Claude." />
      <Tabs items={[{ key: "weights", label: "Weights and calibration" }, { key: "taste", label: "Taste and watch list" }, { key: "rules", label: "Rules and strategy" }]} active={t} onChange={(k) => nav(`/settings/${k}`)} />
      <div className="pt-10">{t === "weights" ? <Weights /> : t === "taste" ? <Taste /> : <Rules />}</div>
    </Page>
  );
}
