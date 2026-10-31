import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import { useBoard } from "../api/hooks";
import type { IdeaSummary } from "../api/types";
import { useActions } from "../components/Actions";
import { useHotkeys } from "../lib/hotkeys";
import { STATUS, VERBS, recommendedVerb } from "../lib/text";
import { AlertDot, Bar60, Button, Empty, ErrorNote, Loading, Page, PageHead } from "../ui/primitives";
import { useToast } from "../ui/toast";

type Filter = "all" | "needs" | "find" | "park";
const BANDS = { fund: "Above the fund line", mid: "Between the park line and the fund line", park: "Below the park line" } as const;

export default function Ideas() {
  const q = useBoard();
  const nav = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const actions = useActions();
  const [filter, setFilter] = useState<Filter>("all");
  const [text, setText] = useState("");
  const [mine, setMine] = useState(false);
  const [order, setOrder] = useState<string[] | null>(null);
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [sel, setSel] = useState(0);
  const [drag, setDrag] = useState<string | null>(null);

  const lines = q.data?.lines ?? { fund: 65, park: 45, ready: 0.34 };
  const rows = useMemo(() => {
    let r = [...(q.data?.rows ?? [])];
    if (text) { const t = text.toLowerCase(); r = r.filter((i) => `${i.title} ${i.thesis}`.toLowerCase().includes(t)); }
    if (filter === "needs") r = r.filter((i) => i.action === "REVIEW_OBJECTION" || i.action === "CONTESTED");
    if (filter === "find") r = r.filter((i) => i.action === "NEED_EVIDENCE");
    if (filter === "park") r = r.filter((i) => i.action === "PARK");
    if (mine) { const o = order ?? (q.data?.rows ?? []).map((i) => i.id); r.sort((a, b) => o.indexOf(a.id) - o.indexOf(b.id)); }
    return r;
  }, [q.data, text, filter, mine, order]);
  const idea = rows[sel];
  const move = (id: string, d: number) => { const o = [...(order ?? (q.data?.rows ?? []).map((i) => i.id))]; const n = o.indexOf(id); const m = n + d; if (n < 0 || m < 0 || m >= o.length) return; [o[n], o[m]] = [o[m], o[n]]; setOrder(o); };
  const dropOn = (to: string) => { if (!drag || drag === to) return; const o = [...(order ?? (q.data?.rows ?? []).map((i) => i.id))]; o.splice(o.indexOf(drag), 1); o.splice(o.indexOf(to), 0, drag); setOrder(o); };

  useHotkeys({
    j: () => setSel((s) => Math.min(rows.length - 1, s + 1)), k: () => setSel((s) => Math.max(0, s - 1)),
    Enter: () => idea && nav(`/ideas/${idea.id}`),
    ...(idea && !mine ? { "1": () => actions.decide(idea, "promote"), "2": () => actions.decide(idea, "need_evidence"), "3": () => actions.decide(idea, "park"), "4": () => actions.decide(idea, "kill") } : {}),
    ...(mine && idea ? { "Alt+ArrowUp": () => move(idea.id, -1), "Alt+ArrowDown": () => move(idea.id, 1) } : {}),
  });

  const save = async () => {
    try { await api.put("/api/my-rank", { idea_ids: order ?? rows.map((r) => r.id) }); toast.show("Your order is saved. The Calibrator reads where you differ from the panel."); qc.invalidateQueries({ queryKey: ["board"] }); }
    catch (e) { toast.show(e instanceof ApiError ? e.detail : "That could not be saved.", { tone: "error", ms: 8000 }); }
  };

  if (q.isLoading) return <Page><Loading rows={8} /></Page>;
  if (q.error) return <Page><ErrorNote error={q.error} retry={() => q.refetch()} /></Page>;
  const all = q.data!.rows;
  const needs = all.filter((i) => i.action === "REVIEW_OBJECTION" || i.action === "CONTESTED").length;
  const band = (s: number | null) => (s == null ? "park" : s >= lines.fund ? "fund" : s >= lines.park ? "mid" : "park");
  const banded = !mine;
  const header = (b: keyof typeof BANDS, n: number) => <tr key={`h-${b}`}><td colSpan={5} className="px-2 pb-2 pt-8"><span className="text-meta font-semibold text-ink-2">{BANDS[b]} ({b === "fund" ? `${lines.fund} and up` : b === "mid" ? `${lines.park} to ${lines.fund - 1}` : `under ${lines.park}`})</span><span className="text-meta text-ink-2"> · {n || "none"}</span></td></tr>;
  const count = (b: string) => rows.filter((r) => band(r.score) === b).length;
  const body: React.ReactNode[] = [];
  let last = "";
  if (banded && !rows.some((r) => band(r.score) === "fund")) body.push(header("fund", 0));
  rows.forEach((i, n) => {
    if (banded && band(i.score) !== last) { last = band(i.score); body.push(header(last as keyof typeof BANDS, count(last))); }
    const rec = VERBS.find((v) => v.id === recommendedVerb(i.action));
    const alert = (i.severity ?? 0) >= 70;
    body.push(
      <tr key={i.id} title={i.id} draggable={mine} onDragStart={() => setDrag(i.id)} onDragOver={(e) => mine && e.preventDefault()} onDrop={() => dropOn(i.id)}
        onClick={() => setSel(n)} className={`h-14 cursor-pointer border-t border-rule ${n === sel ? "bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "hover:bg-surface"} ${pick.has(i.id) ? "bg-sunken" : ""}`}>
        {comparing && <td className="w-10 pl-3"><input type="checkbox" aria-label={`Compare ${i.title}`} checked={pick.has(i.id)} onChange={() => setPick((s) => { const x = new Set(s); x.has(i.id) ? x.delete(i.id) : x.add(i.id); return x; })} /></td>}
        <td className="w-12 px-2 text-ink-2 tnum">{mine ? (order ?? all.map((r) => r.id)).indexOf(i.id) + 1 : i.rank}</td>
        <td className="px-2 py-2">
          <Link to={`/ideas/${i.id}`} className="text-[16px] hover:underline">{i.title}</Link>
          <div className={`flex items-center gap-1.5 text-meta ${alert ? "text-alert" : "text-ink-2"}`}>{alert && <AlertDot />}{i.decision ? `You decided: ${i.decision.action}` : i.action ? STATUS[i.action] : ""}{i.my_rank && i.rank && Math.abs(i.my_rank - i.rank) >= 3 ? ` · you rank it ${i.my_rank}` : ""}</div>
        </td>
        <td className="w-36 px-2"><Bar60 score={i.score} /></td>
        <td className="hidden w-44 px-2 text-ink-2 md:table-cell">{mine ? <span className="space-x-2"><button className="rounded px-2 hover:bg-sunken" aria-label="Move up" onClick={() => move(i.id, -1)}>↑</button><button className="rounded px-2 hover:bg-sunken" aria-label="Move down" onClick={() => move(i.id, 1)}>↓</button></span> : rec?.label}</td>
      </tr>,
    );
  });
  const Seg = ({ v, label }: { v: Filter; label: string }) => <button onClick={() => { setFilter(v); setSel(0); }} className={`h-9 rounded px-3 ${filter === v ? "bg-surface font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}>{label}</button>;

  return (
    <Page>
      <PageHead title="Ideas" sub={`${all.length} ideas on the board. ${all.some((i) => (i.score ?? 0) >= lines.fund) ? "" : "None clears the fund line yet."}`}
        right={comparing && pick.size >= 2 ? <Button kind="primary" onClick={() => nav(`/compare?ids=${[...pick].join(",")}`)}>Compare {pick.size}</Button> : undefined} />
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <input value={text} onChange={(e) => { setText(e.target.value); setSel(0); }} placeholder="Filter" aria-label="Filter ideas" className="h-10 w-56 rounded border border-rule-strong bg-surface px-3 outline-none placeholder:text-ink-2 focus:border-accent" />
        <div className="flex items-center gap-1" role="group" aria-label="Show"><Seg v="all" label="All" /><Seg v="needs" label={`Needs you · ${needs}`} /><Seg v="find" label="Find out first" /><Seg v="park" label="Below the park line" /></div>
        <span className="flex-1" />
        <label className="inline-flex items-center gap-2 text-ink-2"><input type="checkbox" checked={comparing} onChange={(e) => { setComparing(e.target.checked); setPick(new Set()); }} /> Compare</label>
        <label className="inline-flex items-center gap-2 text-ink-2"><input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> My order</label>
        {mine && <Button kind="primary" onClick={save}>Save my order</Button>}
      </div>
      {mine && <p className="mb-2 text-meta text-ink-2">Drag rows, or use the arrows, into the order you would fund them. Where you differ from the panel is the most useful calibration signal there is.</p>}
      {rows.length ? <table className="w-full"><tbody>{body}</tbody></table> : <Empty title="No ideas match" body="Clear the filter to see everything." action={<Button onClick={() => { setText(""); setFilter("all"); }}>Clear filters</Button>} />}
    </Page>
  );
}

export type { IdeaSummary };
