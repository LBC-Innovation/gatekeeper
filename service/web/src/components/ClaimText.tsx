import { Link } from "react-router";
import { humanize, splitClaimRefs, splitIdCodes } from "../lib/text";
import { useOpenRef } from "./RefDialog";

/** Agent prose with plain wording, and "claim 136" turned into a link to the evidence it names. */
/** An ID code in prose (SD-03, PF-0006, IDEA-2026-0031) that opens its at-a-glance card without leaving the page. */
function Codes({ text }: { text: string }) {
  const open = useOpenRef();
  return <>{splitIdCodes(text).map((p, i) => p.code
    ? <button key={i} type="button" onClick={() => open(p.code!)} className="rounded font-mono text-[0.92em] text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-current focus-visible:outline-2" title={`What is ${p.code}?`}>{p.text}</button>
    : <span key={i}>{p.text}</span>)}</>;
}

export function ClaimText({ text, ideaId, claimIds }: { text: string | null | undefined; ideaId?: string; claimIds?: Set<number> }) {
  const parts = splitClaimRefs(humanize(text));
  return (
    <>
      {parts.map((p, i) => {
        if (!p.ids || !ideaId) return <Codes key={i} text={p.text} />;
        let rest = p.text;
        const nodes: React.ReactNode[] = [];
        for (const id of p.ids) {
          const at = rest.indexOf(String(id));
          nodes.push(<Codes key={`${i}-${id}-t`} text={rest.slice(0, at)} />);
          nodes.push(claimIds?.has(id)
            ? <Link key={`${i}-${id}`} className="text-accent underline decoration-accent/40 underline-offset-2 hover:decoration-current" to={`/ideas/${ideaId}?tab=evidence&claim=${id}`}>{id}</Link>
            : String(id));
          rest = rest.slice(at + String(id).length);
        }
        nodes.push(<Codes key={`${i}-end`} text={rest} />);
        return <span key={i}>{nodes}</span>;
      })}
    </>
  );
}
