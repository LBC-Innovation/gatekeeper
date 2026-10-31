import { ClaimText } from "./ClaimText";
import { SectionTitle } from "../ui/primitives";

/** One sentence first. The whole argument is one click away, and never cut off mid-sentence. */
export function CaseBlock({ label, headline, text, alert, none, ideaId, claimIds }: {
  label: string; headline?: string | null; text?: string | null; alert?: boolean; none?: string; ideaId?: string; claimIds?: Set<number>;
}) {
  if (!headline && !text) return <div><SectionTitle>{label}</SectionTitle><p className="text-ink-2">{none ?? "None filed."}</p></div>;
  const head = headline ?? "";
  const more = !!text && text.length > head.length + 5 && text.trim() !== head.trim();
  return (
    <div>
      <SectionTitle alert={alert}>{label}</SectionTitle>
      <p className="serif measure text-lead"><ClaimText text={head || text} ideaId={ideaId} claimIds={claimIds} /></p>
      {more && (
        <details className="mt-2">
          <summary className="text-meta text-accent">Read the full argument</summary>
          <p className="measure mt-2 whitespace-pre-line text-ink-2"><ClaimText text={text} ideaId={ideaId} claimIds={claimIds} /></p>
        </details>
      )}
    </div>
  );
}
