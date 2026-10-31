import { Link, useParams } from "react-router";
import { useRun, useRuns } from "../api/hooks";
import type { RunDetail } from "../api/types";
import { fmtDate, fmtDay, fmtTime } from "../lib/text";
import { ErrorNote, Loading, Page, PageHead } from "../ui/primitives";

const TOOL: Record<string, string> = {
  submit_analyst_review: "Strategy reviews", submit_steward_review: "Portfolio reviews", submit_registrar_review: "Readiness reviews", raise_objection: "Objections",
  submit_candidate: "Drafted ideas", submit_signal: "Signals", curate_signal: "Curation", frame_problem: "Problem statements", add_evidence: "Evidence", annotate_rank: "Rank notes", write_brief: "The brief", update_job: "Job updates",
};
const STAGES: { k: string; label: string; agent: string; match: (a: string, e: string) => boolean; out: (n: number) => string }[] = [
  { k: "scout", label: "Scout", agent: "Scouts", match: (a) => a.startsWith("scout"), out: (n) => `${n} signals filed` },
  { k: "curate", label: "Curate", agent: "Curator", match: (a) => a === "curator", out: (n) => `${n} signals judged` },
  { k: "frame", label: "Frame", agent: "Framer", match: (a) => a === "framer", out: (n) => `${n} problems framed` },
  { k: "invent", label: "Invent", agent: "Inventors", match: (a) => a === "inventor", out: (n) => `${n} ideas drafted` },
  { k: "gate", label: "First screen", agent: "Strategy reviewer", match: (a, e) => a === "analyst" && e.startsWith("gate"), out: (n) => `${n} judged` },
  { k: "panel", label: "Round 1", agent: "The panel and Red Team", match: (a, e) => (e === "review_round1" && a !== "analyst") || e === "objection_raised", out: (n) => `${n} reviews and objections` },
  { k: "round2", label: "Round 2", agent: "The panel", match: (_a, e) => e === "review_round2", out: (n) => `${n} reviews revised` },
  { k: "resolve", label: "Rank", agent: "Arbiter", match: (a) => a === "arbiter", out: (n) => `${n} updates` },
  { k: "brief", label: "Brief", agent: "Herald", match: (_a, e) => e === "run_finished", out: () => "Brief written" },
];
const mins = (a: string, b: string) => Math.max(1, Math.round((new Date(b).getTime() - new Date(a).getTime()) / 60000));

function Detail({ d }: { d: RunDetail }) {
  const run = d.run;
  const live = run.status === "running";
  const rows = STAGES.map((s) => {
    const ev = d.activity.filter((e) => s.match(e.actor, e.event));
    const start = ev.map((e) => e.start).sort()[0], end = ev.map((e) => e.end).sort().slice(-1)[0];
    const reported = d.stages.filter((x) => x.stage === s.k).slice(-1)[0];
    return { ...s, n: ev.reduce((a, e) => a + e.n, 0), start, end, state: live && reported?.status === "running" ? "running" : ev.length ? "done" : live ? "waiting" : "none" };
  });
  const c = run.counts ?? {};
  const rejTotal = d.rejections.reduce((n, r) => n + r.n, 0);
  return (
    <div className="min-w-0 max-w-[820px]">
      <h2 className="text-title">Run {run.id}{live ? ", running" : ""}</h2>
      <p className="mt-1 text-ink-2">{fmtDay(run.started_at)}, {fmtTime(run.started_at)}{run.finished_at ? ` to ${fmtTime(run.finished_at)}` : ""}. {c.signals ?? 0} signals, {c.kept ?? 0} kept, {c.candidates ?? 0} ideas drafted, {c.reviews ?? 0} reviews, {c.objections ?? 0} objections.</p>
      <ol className="mt-6">{rows.filter((r) => r.state !== "none").map((r) => (
        <li key={r.k} className={`grid grid-cols-[24px_130px_1fr_70px] items-baseline gap-4 border-t border-rule py-3 ${r.state === "waiting" ? "text-ink-2" : ""}`}>
          <span aria-hidden>{r.state === "done" ? "✓" : r.state === "running" ? <span className="live-dot inline-block h-2 w-2 rounded-full bg-accent" /> : <span className="inline-block h-2 w-2 rounded-full border border-ink-2" />}</span>
          <span className="font-semibold">{r.label}</span><span>{r.state === "waiting" ? "Waiting" : r.state === "running" ? "Working…" : r.out(r.n)} <span className="text-meta text-ink-2">· {r.agent}</span></span>
          <span className="text-right text-meta text-ink-2 tnum">{r.start && r.state === "done" ? `${mins(r.start, r.end)} min` : ""}</span></li>))}</ol>
      {d.admissions.length > 0 && <p className="mt-6 text-ink-2">{d.admissions.length} ideas were admitted to the full panel. The panel takes {Math.max(5, d.admissions.length)} per run; the rest wait for the next run.</p>}
      <section className="mt-12"><h3 className="mb-1 text-meta font-semibold text-ink-2">Writes the rules turned back: {rejTotal}</h3><p className="mb-3 text-ink-2">Each one was fixed by the agent and filed again.</p>
        {d.rejections.length ? <ul>{d.rejections.map((r) => <li key={r.tool} className="grid grid-cols-[200px_1fr_40px] items-center gap-4 border-t border-rule py-2" title={r.tool}><span>{TOOL[r.tool] ?? r.tool.replace(/_/g, " ")}</span><span className="relative h-1.5 rounded-full bg-sunken"><span className="absolute inset-y-0 left-0 rounded-full bg-ink-2" style={{ width: `${(r.n / d.rejections[0].n) * 100}%` }} /></span><span className="text-right tnum">{r.n}</span></li>)}</ul> : <p className="text-ink-2">None.</p>}
        {d.rejection_samples.length > 0 && <details className="mt-4"><summary className="text-accent">Show sample reasons</summary><ul className="mt-3 space-y-2 font-mono text-meta text-ink-2">{d.rejection_samples.map((s, i) => <li key={i}>{s.tool}: {s.reason}</li>)}</ul></details>}</section>
    </div>
  );
}

export default function Runs() {
  const { id } = useParams();
  const list = useRuns();
  const runId = id ? Number(id) : list.data?.runs[0]?.id;
  const detail = useRun(runId);
  if (list.isLoading) return <Page><Loading rows={6} /></Page>;
  if (list.error) return <Page><ErrorNote error={list.error} retry={() => list.refetch()} /></Page>;
  return (
    <Page>
      <PageHead title="Pipeline runs" sub="What each pass produced, and where the rules turned agents back." />
      <div className="grid gap-8 lg:grid-cols-[220px_1fr] lg:gap-12">
        <ul className="-mx-4 self-start lg:mx-0">{list.data!.runs.map((r) => (
          <li key={r.id}><Link to={`/runs/${r.id}`} className={`block px-4 py-3 ${r.id === runId ? "rounded-l-none rounded-r bg-surface font-semibold shadow-[inset_3px_0_0_var(--accent)]" : "rounded hover:bg-surface"}`}>Run {r.id}{r.status === "running" && <span className="live-dot ml-2 inline-block h-2 w-2 rounded-full bg-accent" aria-label="running" />}<span className="block text-meta font-normal text-ink-2 tnum">{fmtDate(r.started_at)}{r.finished_at ? `, ${mins(r.started_at, r.finished_at)} min` : ""}</span></Link></li>))}</ul>
        {detail.isLoading ? <Loading /> : detail.data ? <Detail d={detail.data} /> : null}
      </div>
    </Page>
  );
}
