import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useSignals } from "../api/hooks";
import { domain, fmtDate, STATUS } from "../lib/text";
import { ErrorNote, Loading, Page, PageHead, SectionTitle } from "../ui/primitives";

const SENSORS: Record<string, string> = { unexpected_occurrences: "Unexpected occurrences", incongruities: "Incongruities", process_needs: "Process needs", industry_market_change: "Industry and market change", demographics: "Demographics", perception_shifts: "Perception shifts", new_knowledge: "New knowledge" };

export default function Signals() {
  const q = useSignals();
  const { id } = useParams();
  const nav = useNavigate();
  const [f, setF] = useState<"all" | "kept" | "dropped">("all");
  if (q.isLoading) return <Page><Loading rows={8} /></Page>;
  if (q.error) return <Page><ErrorNote error={q.error} retry={() => q.refetch()} /></Page>;
  const all = q.data!.signals;
  const rows = all.filter((s) => f === "all" || s.status === f);
  const s = rows.find((x) => x.id === id) ?? rows[0];
  const kept = all.filter((x) => x.status === "kept").length;
  return (
    <Page>
      <PageHead title="Signals" sub={`What the scouts found. ${all.length} filed, ${kept} kept. Each kept signal becomes one problem, and each problem up to six ideas.`} />
      <div className="mb-4 flex gap-1" role="group" aria-label="Show">{(["all", "kept", "dropped"] as const).map((v) => <button key={v} onClick={() => setF(v)} className={`h-9 rounded px-3 ${f === v ? "bg-surface font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}>{v[0].toUpperCase() + v.slice(1)}</button>)}</div>
      <div className="grid gap-8 lg:grid-cols-[360px_1fr] lg:gap-12">
        <ul className="-mx-4 max-h-[75vh] self-start overflow-y-auto lg:mx-0">{rows.map((x) => (
          <li key={x.id}><button onClick={() => nav(`/signals/${x.id}`)} title={x.id} className={`w-full px-4 py-3 text-left ${x.id === s?.id ? "rounded-l-none rounded-r bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "rounded hover:bg-surface"}`}>
            <div className={x.id === s?.id ? "font-semibold" : ""}>{x.title}</div><div className="mt-0.5 text-meta text-ink-2">{x.status === "kept" ? "Kept" : "Dropped"} · {SENSORS[x.sensor] ?? x.sensor} · run {x.run_id}</div></button></li>))}</ul>
        {s && (
          <article className="rise max-w-[760px]" title={s.id}>
            <p className="text-meta text-ink-2">{s.status === "kept" ? "Kept" : "Dropped"} · {SENSORS[s.sensor] ?? s.sensor}</p>
            <h2 className="mt-1 text-title">{s.title}</h2>
            <p className="mt-2 text-meta text-ink-2"><a href={s.url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{domain(s.url)}</a>, retrieved {fmtDate(s.retrieved_at)}</p>
            <blockquote className="serif mt-6 border-l-2 border-rule-strong pl-5 text-lead">{s.excerpt}</blockquote>
            {s.curator_note && <section className="mt-8"><SectionTitle>{s.status === "kept" ? "Why the curator kept it" : "Why the curator dropped it"}</SectionTitle><p>{s.curator_note}</p></section>}
            {s.problem && <section className="mt-8"><SectionTitle>The problem it became</SectionTitle><p>{s.problem.statement}</p><p className="mt-1 text-meta text-ink-2">For {s.problem.for_whom}</p></section>}
            {s.ideas.length > 0 && <section className="mt-8"><SectionTitle>{s.ideas.length} ideas drafted from it</SectionTitle>
              <ul>{s.ideas.map((i) => <li key={i.id} className="flex items-baseline gap-4 border-t border-rule py-3"><Link to={`/ideas/${i.id}`} className="flex-1 hover:underline">{i.title}</Link><span className="text-meta text-ink-2">{i.action ? STATUS[i.action] : i.stage === "parked_auto" ? "Parked at the first screen" : "Waiting"}</span><span className="w-8 text-right tnum">{i.score ?? ""}</span></li>)}</ul></section>}
          </article>
        )}
      </div>
    </Page>
  );
}
