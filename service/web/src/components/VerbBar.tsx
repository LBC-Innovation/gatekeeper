import { useNavigate } from "react-router";
import type { IdeaSummary } from "../api/types";
import { usePendingVerb } from "../lib/pending";
import { OUTCOME, VERBS, recommendedVerb } from "../lib/text";
import { Button } from "../ui/primitives";
import { useActions } from "./Actions";

/** Four verbs, the panel's pick filled. Everything else sits behind one "More". */
export function VerbBar({ idea, hasOpenObjection, showOpen }: { idea: IdeaSummary; hasOpenObjection: boolean; showOpen?: boolean }) {
  const a = useActions();
  const nav = useNavigate();
  const pending = usePendingVerb(idea.id);
  const rec = recommendedVerb(idea.action);
  const done = pending ?? idea.decision?.action;
  if (done) {
    return <p className="text-positive">You decided: <b>{OUTCOME[done] ?? done}</b>.{idea.decision?.reason ? <span className="text-ink-2"> “{idea.decision.reason}”</span> : <span className="text-ink-2"> Recording in a moment.</span>}</p>;
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      {VERBS.map((v) => <Button key={v.id} kind={v.id === rec ? "primary" : "secondary"} kbd={v.key} onClick={() => a.decide(idea, v.id)}>{v.label}</Button>)}
      <details className="relative">
        <summary className="inline-flex h-10 items-center rounded px-3 text-accent hover:bg-sunken">More</summary>
        <div className="absolute left-0 z-20 mt-1 w-64 rounded-md border border-rule-strong bg-surface py-2 shadow-lg">
          {hasOpenObjection && <button className="block w-full px-4 py-2 text-left hover:bg-sunken" onClick={() => a.answer(idea)}>Answer the objection <span className="kbd ml-1">a</span></button>}
          <button className="block w-full px-4 py-2 text-left hover:bg-sunken" onClick={() => a.evidence(idea)}>Ask for evidence <span className="kbd ml-1">r</span></button>
          {showOpen && <button className="block w-full px-4 py-2 text-left hover:bg-sunken" onClick={() => nav(`/ideas/${idea.id}`)}>Open the full record <span className="kbd ml-1">↵</span></button>}
          <button className="block w-full px-4 py-2 text-left hover:bg-sunken" onClick={() => a.claude(idea, hasOpenObjection ? "objection" : "idea")}>Discuss in Claude</button>
        </div>
      </details>
    </div>
  );
}
