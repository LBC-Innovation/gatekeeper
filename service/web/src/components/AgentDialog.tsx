import { useState } from "react";
import { useAgent } from "../api/hooks";
import { Markdown, splitFrontmatter } from "../lib/markdown";
import { Button, Dialog, Loading } from "../ui/primitives";
import { useToast } from "../ui/toast";

/** An agent's instruction file, as it is on disk. Rendered for reading, or as raw source for close analysis. */
export function AgentDialog({ id, onClose }: { id: string; onClose: () => void }) {
  const q = useAgent(id);
  const toast = useToast();
  const [view, setView] = useState<"read" | "source">("read");
  const a = q.data;
  const { body } = a?.markdown ? splitFrontmatter(a.markdown) : { body: "" };
  const Seg = ({ v, label }: { v: "read" | "source"; label: string }) => (
    <button onClick={() => setView(v)} aria-pressed={view === v} className={`h-9 rounded px-3 ${view === v ? "bg-sunken font-semibold" : "text-ink-2 hover:text-ink"}`}>{label}</button>
  );
  return (
    <Dialog onClose={onClose} label={a ? `${a.name}: instructions` : "Agent instructions"} wide>
      <div className="flex items-start gap-4 border-b border-rule p-5">
        {a && <img src={a.avatar} alt="" width={64} height={64} className="h-16 w-16 shrink-0 rounded-full" />}
        <div className="min-w-0 flex-1">
          <h2 className="text-title leading-tight">{a?.name ?? "…"}{a && <span className="ml-3 text-lead font-normal text-ink-2">{a.epithet}</span>}</h2>
          {a?.file && <p className="mt-1 font-mono text-[13px] text-ink-2">{a.file}</p>}
        </div>
        <button onClick={onClose} aria-label="Close" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded text-ink-2 hover:bg-sunken hover:text-ink">✕</button>
      </div>
      <div className="flex items-center gap-1 border-b border-rule px-5 py-2">
        <Seg v="read" label="Read" /><Seg v="source" label="Source" />
        <span className="flex-1" />
        {a?.markdown && <Button kind="ghost" onClick={async () => { await navigator.clipboard?.writeText(a.markdown ?? ""); toast.show("File copied."); }}>Copy file</Button>}
      </div>
      <div className="max-h-[62vh] overflow-y-auto p-5">
        {q.isLoading && <Loading rows={5} />}
        {a && !a.markdown && <p className="text-ink-2">This agent's file was not found at {a.file ?? "claude-config/agents"}.</p>}
        {a?.markdown && view === "source" && <pre className="whitespace-pre-wrap font-mono text-[13px] leading-5">{a.markdown}</pre>}
        {a?.markdown && view === "read" && (
          <>
            <section className="mb-6 rounded border border-rule bg-sunken p-4">
              <h3 className="mb-2 text-meta font-semibold text-ink-2">What this agent can touch</h3>
              <dl className="grid gap-x-4 gap-y-1 text-[14px] md:grid-cols-[120px_1fr]">
                <dt className="text-ink-2">Model</dt><dd>{a.model ?? "default"}</dd>
                <dt className="text-ink-2">The web</dt><dd>{a.can_search_web ? "Can search and read pages" : "No access"}</dd>
                <dt className="text-ink-2">The ledger</dt><dd className="font-mono text-[13px] leading-5">{a.tools.ledger.join(", ") || "none"}</dd>
                {a.tools.other.filter((t) => t !== "WebSearch" && t !== "WebFetch").length > 0 && (<><dt className="text-ink-2">Other</dt><dd>{a.tools.other.filter((t) => t !== "WebSearch" && t !== "WebFetch").join(", ")}</dd></>)}
              </dl>
            </section>
            <Markdown text={body} />
          </>
        )}
      </div>
    </Dialog>
  );
}
