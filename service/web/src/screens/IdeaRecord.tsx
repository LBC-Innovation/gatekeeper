import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { useBoard, useIdea } from "../api/hooks";
import type { IdeaRecord as Rec, Review } from "../api/types";
import { useActions } from "../components/Actions";
import { CaseBlock } from "../components/CaseBlock";
import { ClaimText } from "../components/ClaimText";
import { VerbBar } from "../components/VerbBar";
import { useHotkeys } from "../lib/hotkeys";
import { defaultSentence, domain, fmtDate, fmtTime, humanize, OUTCOME, STATUS, strengthWord } from "../lib/text";
import { AlertDot, Button, Empty, ErrorNote, Loading, Page, SectionTitle, StrengthLine, Tabs } from "../ui/primitives";

type Tab = "case" | "panel" | "objections" | "evidence" | "origin" | "history";
const WHO: Record<string, string> = { analyst: "Strategy reviewer", steward: "Portfolio reviewer", registrar: "Readiness reviewer", redteam: "Red Team", arbiter: "Arbiter", inventor: "Inventor", orchestrator: "The pipeline", human: "You" };
const EVENT: Record<string, string> = {
  candidate_submitted: "Idea drafted", gate_passed: "Passed the first screen", gate_parked: "Parked at the first screen", review_round1: "Reviewed, round 1", review_round2: "Reviewed again, round 2",
  objection_raised: "Objection raised", on_board: "Reached the board", panel_admitted: "Admitted to the panel", queue_reconciled: "Queue updated", evidence_added: "Evidence added",
  decision_promote: "You funded the check", decision_park: "You parked it", decision_kill: "You killed it", decision_need_evidence: "You asked to find out first", objection_answered: "You answered the objection",
};

function ReviewCard({ role, reviews, rec }: { role: Review["role"]; reviews: Review[]; rec: Rec }) {
  const rs = reviews.filter((r) => r.role === role).sort((a, b) => a.round - b.round);
  if (!rs.length) return null;
  const r1 = rs[0], r2 = rs[rs.length - 1];
  const moved = rs.length > 1 && r2.score !== r1.score;
  const ids = new Set(rec.evidence.map((c) => c.id));
  const title = { analyst: "Strategy", steward: "Portfolio", registrar: "Readiness" }[role];
  const a = rec.analyst, s = rec.steward;
  return (
    <section className="border-t border-rule py-5" aria-label={`${title} reviewer`}>
      <header className="flex flex-wrap items-baseline gap-3">
        <h3 className="text-lead">{title}</h3>
        <span className="text-meta text-ink-2">{role === "registrar" ? "Readiness does not vote" : WHO[role]}</span>
        <span className="ml-auto tnum">{rs.length > 1 && <span className="text-ink-2">{Math.round(r1.score)} → </span>}<b className="font-semibold">{role === "registrar" ? `${rec.readiness.total} of ${rec.readiness.max}` : r2.score}</b>
          {moved ? <span className="ml-2 text-meta text-ink-2">{r2.score < r1.score ? "down" : "up"} {Math.abs(r2.score - r1.score)}</span> : rs.length > 1 ? <span className="ml-2 text-meta text-ink-2">held</span> : null}</span>
      </header>
      <p className="serif measure mt-2 text-lead"><ClaimText text={r2.headline} ideaId={rec.summary.id} claimIds={ids} /></p>
      {role === "analyst" && a && (
        <div className="mt-3 space-y-1 text-ink-2">
          <p>Fit with strategy {a.fit}{a.round1_fit != null && a.round1_fit !== a.fit ? ` (was ${a.round1_fit})` : ""}. Capability {a.capability}.{a.directive_id ? ` Serves ${a.directive_id}.` : ""}</p>
          {a.constraints.filter((c) => c.applies).map((c) => <p key={c.rule} className="text-ink">No-path gap: {c.capabilities.join(", ")} has no way to be acquired, so capability is held at or below {Math.round(c.ceiling * 100)}{c.binding ? " (this lowered the score)." : " (it was already lower)."}</p>)}
          {a.gaps.length > 0 && <ul className="mt-2">{a.gaps.map((g, i) => <li key={i}>{g.capability} <span className="text-meta">· {g.acquisition_path === "none" ? "no path to close it" : `${g.acquisition_path} it`}</span></li>)}</ul>}
        </div>
      )}
      {role === "steward" && s && (
        <p className="mt-3 text-ink-2">{(s.mix_effect ?? 0) > 0 ? "Moves the mix toward your aim." : "Moves the mix away from your aim."} Risk of taking business from live work: {s.cannibalization} of 100.{s.overlaps.length ? ` Overlaps ${s.overlaps.map((o) => o.name).join(", ")}.` : ""}</p>
      )}
      {role === "registrar" && (
        <ul className="mt-3">{rec.readiness.dims.map((d) => (
          <li key={d.key} className="grid gap-x-6 border-t border-rule py-2 md:grid-cols-[200px_1fr]"><span className={d.score >= 2 ? "" : "text-ink-2"}>{d.label}: {d.word}</span><span className="text-ink-2">{d.gap && <ClaimText text={d.gap} ideaId={rec.summary.id} claimIds={ids} />}{d.owner_hint ? ` · ${d.owner_hint}` : ""}</span></li>))}</ul>
      )}
      {rs.length > 1 && r2.revision_reason && (
        <div className="mt-3 rounded bg-sunken p-3"><p className="text-meta font-semibold text-ink-2">{moved ? "Why it moved in round 2" : "Why it held in round 2"}</p><p className="text-ink-2"><ClaimText text={r2.revision_reason} ideaId={rec.summary.id} claimIds={ids} /></p></div>
      )}
      <details className="mt-3"><summary className="text-meta text-accent">Read the full rationale{rs.length > 1 ? " (round 2)" : ""}</summary>
        <p className="measure mt-2 text-ink-2"><ClaimText text={r2.rationale} ideaId={rec.summary.id} claimIds={ids} /></p>
        {rs.length > 1 && <><p className="mt-3 text-meta text-ink-2">Round 1</p><p className="measure text-meta text-ink-2"><ClaimText text={r1.rationale} ideaId={rec.summary.id} claimIds={ids} /></p></>}</details>
    </section>
  );
}

export default function IdeaRecord() {
  const { id } = useParams();
  const [sp, setSp] = useSearchParams();
  const tab = (sp.get("tab") as Tab) || "case";
  const nav = useNavigate();
  const actions = useActions();
  const q = useIdea(id);
  const board = useBoard();
  const rec = q.data;
  useHotkeys(rec ? { j: () => rec.board_neighbours.next && nav(`/ideas/${rec.board_neighbours.next}?tab=${tab}`), k: () => rec.board_neighbours.prev && nav(`/ideas/${rec.board_neighbours.prev}?tab=${tab}`),
    u: () => nav(-1), "]": () => go(1), "[": () => go(-1),
    ...(!rec.summary.decision ? { "1": () => actions.decide(rec.summary, "promote"), "2": () => actions.decide(rec.summary, "need_evidence"), "3": () => actions.decide(rec.summary, "park"), "4": () => actions.decide(rec.summary, "kill") } : {}),
    a: () => actions.answer(rec.summary), r: () => actions.evidence(rec.summary) } : {});
  const ORDER: Tab[] = ["case", "panel", "objections", "evidence", "origin", "history"];
  const go = (d: number) => setSp({ tab: ORDER[(ORDER.indexOf(tab) + d + ORDER.length) % ORDER.length] });

  if (q.isLoading) return <Page><Loading rows={6} /></Page>;
  if (q.error || !rec) return <Page><ErrorNote error={q.error ?? new Error("That idea was not found.")} retry={() => q.refetch()} /></Page>;
  const s = rec.summary;
  const lines = board.data?.lines ?? { fund: 65, park: 45, ready: 0.34 };
  const open = rec.objections.find((o) => o.status === "open");
  const ids = new Set(rec.evidence.map((c) => c.id));
  const analyst = [...rec.reviews].filter((r) => r.role === "analyst").sort((a, b) => b.round - a.round)[0];
  const severe = (open?.severity ?? 0) >= 70;
  const summary = s.score == null ? "Not scored yet." : `Strength ${s.score} of 100, ${strengthWord(s.score, lines.fund, lines.park)}.${severe && open ? ` Serious objection open: ${open.headline}` : ""}`;
  const nb = rec.board_neighbours;
  const claimId = Number(sp.get("claim")) || null;
  const tabs: { key: Tab; label: string; n?: number }[] = [{ key: "case", label: "The case" }, { key: "panel", label: "How the panel scored it" }, { key: "objections", label: "Objections", n: rec.objections.length }, { key: "evidence", label: "Evidence", n: rec.evidence.length }, { key: "origin", label: "Where it came from" }, { key: "history", label: "History", n: rec.timeline.length }];
  const ev = sp.get("kind") ?? "all";

  return (
    <Page>
      <div className="mb-6 flex items-center justify-between text-meta text-ink-2">
        <button onClick={() => nav(-1)} className="hover:text-ink">← Back</button>
        {nb.position && <span className="tnum">Rank {nb.position} of {nb.of}</span>}
      </div>
      <header className="mb-8" title={s.id}>
        <h1 className="text-title md:text-display">{s.title}</h1>
        <p className="measure mt-3 text-ink-2">{s.thesis}</p>
        <p className="serif measure mt-5 text-lead"><ClaimText text={summary} ideaId={s.id} claimIds={ids} /></p>
        <StrengthLine score={s.score} fund={lines.fund} park={lines.park} />
      </header>
      <div className="sticky top-14 z-10 -mx-4 mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 border-y border-rule bg-canvas/95 px-4 py-3 backdrop-blur md:-mx-12 md:px-12">
        <VerbBar idea={s} hasOpenObjection={!!open} />
        <span className="text-meta text-ink-2 md:ml-auto">{s.queue ? defaultSentence(s.queue) : "Not in your queue."}</span>
      </div>
      <Tabs items={tabs} active={tab} onChange={(k) => setSp({ tab: k })} />
      <div className="pt-8" role="tabpanel">
        {tab === "case" && (
          <div className="max-w-[760px] space-y-10">
            <CaseBlock label="The case for" headline={analyst?.headline} text={analyst?.rationale} ideaId={s.id} claimIds={ids} />
            <CaseBlock label="The case against" headline={open?.headline} text={open?.text} alert={severe} none="No objection filed." ideaId={s.id} claimIds={ids} />
            {open && <div className="-mt-6 flex flex-wrap gap-2"><Button onClick={() => actions.answer(s, open)}>Answer it</Button><Button kind="ghost" onClick={() => actions.evidence(s, open.falsifier)}>Go find out</Button></div>}
            <section><SectionTitle>Cheapest check</SectionTitle><p className="serif text-lead">{rec.first_check?.smallest_commitment ?? "Not defined yet."}</p>
              {rec.first_check?.uncertainty_retired && <p className="mt-3 text-ink-2"><span className="text-ink">It would settle:</span> {rec.first_check.uncertainty_retired}</p>}
              {rec.first_check?.what_must_be_true && <p className="mt-2 text-ink-2"><span className="text-ink">To go further:</span> {rec.first_check.what_must_be_true}</p>}</section>
            <section><SectionTitle>Is the check ready to run?</SectionTitle><p className="mb-3">{rec.readiness.enough ? "Yes, it is defined well enough to run, with the gaps below." : "Not yet. The gaps below need closing first."}</p>
              <ul>{rec.readiness.dims.map((d) => <li key={d.key} className="grid gap-x-6 border-t border-rule py-2 md:grid-cols-[200px_1fr]"><span className={d.score >= 2 ? "" : "text-ink-2"}>{d.label}: {d.word}</span><span className="text-ink-2"><ClaimText text={d.gap} ideaId={s.id} claimIds={ids} /></span></li>)}</ul></section>
            {open && <section><SectionTitle>What would change our mind</SectionTitle><p className="text-ink-2"><ClaimText text={open.falsifier} ideaId={s.id} claimIds={ids} /></p></section>}
          </div>
        )}
        {tab === "panel" && (
          <div className="max-w-[820px]">
            {rec.arithmetic && <details className="mb-6"><summary className="text-accent">Show the maths</summary><p className="mt-3 font-mono text-meta text-ink-2">{rec.arithmetic}</p></details>}
            <ReviewCard role="analyst" reviews={rec.reviews} rec={rec} /><ReviewCard role="steward" reviews={rec.reviews} rec={rec} /><ReviewCard role="registrar" reviews={rec.reviews} rec={rec} />
          </div>
        )}
        {tab === "objections" && (rec.objections.length === 0 ? <Empty title="No objections" body="Red Team has not filed on this idea yet." /> : (
          <div className="max-w-[820px]">{rec.objections.map((o) => (
            <section key={o.id} className={`border-t border-rule py-6 ${o.status !== "open" ? "opacity-70" : ""}`}>
              <p className="flex items-center gap-2 text-meta text-ink-2">{o.severity >= 70 && o.status === "open" && <AlertDot />}{o.severity >= 70 ? "Serious" : o.severity >= 40 ? "Moderate" : "Low"} objection · {o.status === "open" ? "open" : o.status} · Red Team, {fmtDate(o.created_at)}</p>
              <p className="serif mt-1 text-lead"><ClaimText text={o.headline} ideaId={s.id} claimIds={ids} /></p>
              <details className="mt-2"><summary className="text-meta text-accent">Read the full argument</summary><p className="measure mt-2 text-ink-2"><ClaimText text={o.text} ideaId={s.id} claimIds={ids} /></p></details>
              <div className="mt-3 rounded bg-sunken p-3"><p className="text-meta font-semibold text-ink-2">What would change our mind</p><p className="text-ink-2"><ClaimText text={o.falsifier} ideaId={s.id} claimIds={ids} /></p></div>
              {o.answer && o.status !== "superseded" && <p className="mt-3 text-ink-2">Your answer ({o.status}): “{o.answer}”</p>}
              {o.status === "open" && <div className="mt-3 flex gap-2"><Button onClick={() => actions.answer(s, o)}>Answer it</Button><Button kind="ghost" onClick={() => actions.evidence(s, o.falsifier)}>Go find out</Button></div>}
            </section>))}</div>
        ))}
        {tab === "evidence" && (rec.evidence.length === 0 ? <Empty title="No claims yet" body="Every figure on this idea will appear here with its source or its estimate basis." /> : (
          <div className="max-w-[900px]">
            <div className="mb-4 flex gap-2">{["all", "source", "estimate"].map((k) => <button key={k} onClick={() => setSp({ tab: "evidence", kind: k })} className={`h-9 rounded px-3 ${ev === k ? "bg-ink text-canvas" : "bg-sunken text-ink-2"}`}>{{ all: `All ${rec.evidence.length}`, source: `Sourced ${rec.evidence.filter((c) => c.kind === "source").length}`, estimate: `Estimates ${rec.evidence.filter((c) => c.kind === "estimate").length}` }[k]}</button>)}</div>
            <ul>{rec.evidence.filter((c) => ev === "all" || c.kind === ev).map((c) => (
              <li key={c.id} id={`claim-${c.id}`} ref={(el) => { if (el && c.id === claimId) el.scrollIntoView({ block: "center" }); }} className={`border-t border-rule py-4 ${c.id === claimId ? "bg-sunken" : ""}`}>
                <p>{c.statement}</p>
                <p className="mt-1 text-meta text-ink-2">{c.kind === "source" ? <>Source: <a className="text-accent hover:underline" target="_blank" rel="noopener noreferrer" href={c.url ?? "#"}>{domain(c.url ?? "")}</a>, retrieved {fmtDate(c.retrieved_at)}</> : <>Estimate, {c.confidence} confidence. {c.basis}</>} · claim {c.id}</p>
                {c.excerpt && <details><summary className="mt-1 text-meta text-accent">Quoted passage</summary><blockquote className="mt-1 border-l-2 border-rule-strong pl-3 text-ink-2">{c.excerpt}</blockquote></details>}
              </li>))}</ul>
          </div>
        ))}
        {tab === "origin" && (
          <div className="max-w-[760px] space-y-8">
            {rec.signal && <section><SectionTitle>The signal</SectionTitle><p className="text-lead serif">{rec.signal.title}</p><p className="mt-1 text-meta text-ink-2"><a className="text-accent hover:underline" href={rec.signal.url} target="_blank" rel="noopener noreferrer">{domain(rec.signal.url)}</a>, retrieved {fmtDate(rec.signal.retrieved_at)}</p><blockquote className="mt-3 border-l-2 border-rule-strong pl-4 text-ink-2">{rec.signal.excerpt}</blockquote></section>}
            {rec.problem && <section><SectionTitle>The problem it became</SectionTitle><p>{rec.problem.statement}</p><p className="mt-1 text-meta text-ink-2">For {rec.problem.for_whom}. Why now: {rec.problem.why_now}</p></section>}
            <section><SectionTitle>Ideas drafted from the same problem</SectionTitle><ul>{rec.siblings.map((x) => <li key={x.id} className="flex items-baseline gap-4 border-t border-rule py-3"><span className="flex-1">{x.id === s.id ? <b>{x.title}</b> : <Link className="hover:underline" to={`/ideas/${x.id}`}>{x.title}</Link>}</span><span className="text-meta text-ink-2">{x.action ? STATUS[x.action] : x.stage === "parked_auto" ? "Parked at the first screen" : "Waiting"}</span><span className="w-8 text-right tnum">{x.score ?? ""}</span></li>)}</ul></section>
          </div>
        )}
        {tab === "history" && (
          <ol className="max-w-[820px]">
            {[...rec.timeline].reverse().map((e) => <li key={e.id} className="grid gap-x-6 border-t border-rule py-3 md:grid-cols-[150px_150px_1fr]"><span className="text-meta text-ink-2 tnum">{fmtDate(e.at)} {fmtTime(e.at)}</span><span className="text-meta text-ink-2">{WHO[e.actor] ?? humanize(e.actor)}</span><span>{EVENT[e.event] ?? humanize(e.event)}{e.detail?.reason ? <span className="text-ink-2">: “{e.detail.reason}”</span> : ""}</span></li>)}
            {rec.decisions.length === 0 && rec.timeline.length === 0 && <Empty title="Nothing yet" />}
          </ol>
        )}
      </div>
      {s.decision && <p className="mt-10 text-meta text-ink-2">{OUTCOME[s.decision.action] ?? s.decision.action} by {s.decision.actor === "human" ? "you" : "default"} on {fmtDate(s.decision.at)}.</p>}
    </Page>
  );
}
