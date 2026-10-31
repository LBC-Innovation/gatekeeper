import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useIdea, useInbox } from "../api/hooks";
import type { IdeaRecord, InboxItem } from "../api/types";
import { useActions } from "../components/Actions";
import { CaseBlock } from "../components/CaseBlock";
import { VerbBar } from "../components/VerbBar";
import { useHotkeys } from "../lib/hotkeys";
import { defaultSentence, defaultUpdate, fmtDay, plural } from "../lib/text";
import { useMedia } from "../lib/useMedia";
import { AlertDot, Empty, ErrorNote, Loading, Page, SectionTitle } from "../ui/primitives";

/** The panel's advice as one sentence a person can act on. */
function recSentence(action: string | null): string {
  switch (action) {
    case "REVIEW_OBJECTION": return "The panel wants you to weigh a serious objection before anything moves. It suggests finding out first.";
    case "CONTESTED": return "The two voting reviewers disagree. The panel suggests finding out first, because the cheapest check below would settle it.";
    case "NEED_EVIDENCE": return "The idea is in range, but the check is not yet defined well enough to fund. The panel suggests finding out first.";
    case "CONSIDER": return "The panel leans towards funding the check. It is your call.";
    case "PROMOTE": return "The panel recommends funding the check.";
    case "PARK": return "It scores below the park line. The panel suggests parking it.";
    default: return "";
  }
}
const SAY: Record<string, string> = { CONTESTED: "Split panel", REVIEW_OBJECTION: "Serious objection", NEED_EVIDENCE: "Panel says find out first", CONSIDER: "Panel leans yes", PARK: "Below the park line", PROMOTE: "Panel says fund" };

function Row({ item, selected, wide, onSelect }: { item: InboxItem; selected: boolean; wide: boolean; onSelect: () => void }) {
  const i = item.idea;
  const alert = !i.decision && item.kind === "objection";
  const line = i.decision ? "Decided" : SAY[item.queue.recommended_action] ?? "";
  const update = i.decision ? null : defaultUpdate(item.queue);
  const body = (
    <>
      <div className={`text-[16px] leading-6 ${selected ? "font-semibold" : ""}`}>{i.title}</div>
      <div className="mt-0.5 flex items-center gap-1.5 text-meta text-ink-2">{alert && <AlertDot />}{line}</div>
      {update && <div className={`text-meta text-ink-2 ${alert ? "pl-3.5" : ""}`}>{update[0].toUpperCase() + update.slice(1)}</div>}
    </>
  );
  const cls = `block w-full px-4 py-3 text-left ${selected ? "rounded-l-none rounded-r bg-surface shadow-[inset_3px_0_0_var(--accent)]" : "rounded hover:bg-surface"} ${i.decision ? "opacity-50" : ""}`;
  return wide
    ? <button className={cls} onClick={onSelect} aria-current={selected} title={i.id}>{body}</button>
    : <Link className={cls} to={`/ideas/${i.id}`} title={i.id}>{body}</Link>;
}

function Detail({ item }: { item: InboxItem }) {
  const { data: rec, isLoading } = useIdea(item.idea.id);
  const i = item.idea;
  return (
    <article className="rise" aria-labelledby="dc-title" title={i.id}>
      <h2 id="dc-title" className="text-title"><Link to={`/ideas/${i.id}`} className="decoration-1 underline-offset-4 hover:underline">{i.title}</Link></h2>
      <p className="measure mt-2 text-ink-2">{i.thesis}</p>
      <p className="serif measure mt-5 text-lead">{recSentence(i.action)}</p>
      <p className="mt-3 text-meta text-ink-2">{defaultSentence(item.queue)}</p>
      <div className="mt-4"><VerbBar idea={i} hasOpenObjection={i.severity != null} showOpen /></div>
      <div className="mt-10 space-y-6 border-t border-rule pt-6">
        {isLoading || !rec ? <Loading rows={3} /> : <Cases rec={rec} />}
      </div>
    </article>
  );
}

function Cases({ rec }: { rec: IdeaRecord }) {
  const analyst = [...rec.reviews].filter((r) => r.role === "analyst").sort((a, b) => b.round - a.round)[0];
  const open = rec.objections.find((o) => o.status === "open");
  const ids = new Set(rec.evidence.map((c) => c.id));
  return (
    <>
      <CaseBlock label="The case for" headline={analyst?.headline} text={analyst?.rationale} ideaId={rec.summary.id} claimIds={ids} />
      <CaseBlock label="The case against" headline={open?.headline} text={open?.text} alert={(open?.severity ?? 0) >= 70} none="No objection filed." ideaId={rec.summary.id} claimIds={ids} />
      <div><SectionTitle>Cheapest check</SectionTitle><p className="measure">{rec.first_check?.smallest_commitment ?? "Not defined yet."}</p></div>
    </>
  );
}

export default function Today() {
  const q = useInbox();
  const wide = useMedia("(min-width: 1024px)");
  const nav = useNavigate();
  const actions = useActions();
  const [selId, setSelId] = useState<string | null>(null);
  const items = q.data?.items ?? [];
  const objections = items.filter((x) => x.kind === "objection");
  const decisions = items.filter((x) => x.kind === "decision");
  const ordered = useMemo(() => [...objections, ...decisions], [items]); // eslint-disable-line react-hooks/exhaustive-deps
  const selected = ordered.find((x) => x.idea.id === selId) ?? ordered.find((x) => !x.idea.decision) ?? ordered[0];
  useEffect(() => { if (selected && selected.idea.id !== selId) setSelId(selected.idea.id); }, [selected, selId]);
  const move = (d: number) => { const n = ordered.findIndex((x) => x.idea.id === selected?.idea.id); const nx = ordered[Math.max(0, Math.min(ordered.length - 1, n + d))]; if (nx) setSelId(nx.idea.id); };
  const idea = selected?.idea;
  useHotkeys(wide && idea ? {
    j: () => move(1), k: () => move(-1), Enter: () => nav(`/ideas/${idea.id}`),
    "1": () => actions.decide(idea, "promote"), "2": () => actions.decide(idea, "need_evidence"), "3": () => actions.decide(idea, "park"), "4": () => actions.decide(idea, "kill"),
    a: () => actions.answer(idea), r: () => actions.evidence(idea),
  } : {});

  if (q.isLoading) return <Page><Loading /></Page>;
  if (q.error) return <Page><ErrorNote error={q.error} retry={() => q.refetch()} /></Page>;
  const d = q.data!;
  const open = items.filter((x) => !x.idea.decision);
  const nObj = open.filter((x) => x.kind === "objection").length, nDec = open.filter((x) => x.kind === "decision").length;
  const heading = nObj + nDec === 0 ? "Nothing needs you today." : [nDec ? plural(nDec, "decision") : "", nObj ? plural(nObj, "objection") : ""].filter(Boolean).join(", ");
  const earliest = [...open].sort((a, b) => a.queue.default_on.localeCompare(b.queue.default_on))[0];

  const group = (label: string, list: InboxItem[]) => list.length > 0 && (
    <div className="mb-6"><h2 className="mb-1 px-4 text-meta font-semibold text-ink-2" style={{ fontFamily: "var(--font-sans)", fontWeight: 600 }}>{label}</h2>
      <ul>{list.map((it) => <li key={it.idea.id}><Row item={it} wide={wide} selected={wide && it.idea.id === selected?.idea.id} onSelect={() => setSelId(it.idea.id)} /></li>)}</ul></div>
  );

  return (
    <Page>
      <header className="mb-10">
        <h1 className="text-display">{heading}</h1>
        <p className="measure mt-2 text-ink-2">
          {earliest ? `The earliest automatic status update is ${fmtDay(earliest.queue.default_on)}. ` : ""}
          {!d.portfolio.in_band && <>The book is out of balance. <Link to="/portfolio" className="text-accent hover:underline">See where</Link>. </>}
          <Link to="/log" className="text-accent hover:underline">What else happened</Link>
        </p>
        {d.brief && !d.brief.quiet && (
          <details className="mt-3 max-w-[760px]"><summary className="text-meta text-accent">Read the brief from {fmtDay(d.brief.date)}</summary>
            <pre className="mt-2 whitespace-pre-wrap font-sans text-meta text-ink-2">{d.brief.body}</pre></details>
        )}
      </header>
      {items.length === 0 ? <Empty title="You are clear" body="Nothing else needs you before the next run." action={<Link to="/ideas" className="text-accent hover:underline">Browse the ideas</Link>} /> : (
        <div className="grid gap-8 lg:grid-cols-[320px_1fr] lg:gap-12">
          <nav aria-label="Queue" className="-mx-4 self-start lg:sticky lg:top-20 lg:mx-0">
            {group("Serious objections", objections)}
            {group("Decisions", decisions)}
          </nav>
          {wide && selected && <div className="min-w-0"><Detail item={selected} /></div>}
        </div>
      )}
    </Page>
  );
}
