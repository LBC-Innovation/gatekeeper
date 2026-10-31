import { useQueries } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import { api } from "../api/client";
import type { IdeaRecord } from "../api/types";
import { CELLS, STATUS, humanize } from "../lib/text";
import { Bar60, Empty, Loading, Page, PageHead } from "../ui/primitives";

export default function Compare() {
  const [sp] = useSearchParams();
  const ids = (sp.get("ids") ?? "").split(",").filter(Boolean).slice(0, 4);
  const results = useQueries({ queries: ids.map((id) => ({ queryKey: ["idea", id], queryFn: () => api.get<IdeaRecord>(`/api/ideas/${id}`) })) });
  if (ids.length < 2) return <Page><Empty title="Pick two to four ideas" body="On Ideas, turn on Compare, tick the ideas, then choose Compare." action={<Link className="text-accent hover:underline" to="/ideas">Go to Ideas</Link>} /></Page>;
  if (results.some((r) => r.isLoading)) return <Page><Loading rows={6} /></Page>;
  const recs = results.map((r) => r.data).filter((x): x is IdeaRecord => !!x);
  const top = Math.max(...recs.map((r) => r.summary.score ?? 0));
  const row = (label: string, fn: (r: IdeaRecord) => React.ReactNode) => (
    <tr className="border-t border-rule align-top"><th scope="row" className="w-40 py-5 pr-6 text-left text-meta font-semibold text-ink-2">{label}</th>{recs.map((r) => <td key={r.summary.id} className="px-4 py-5">{fn(r)}</td>)}</tr>
  );
  return (
    <Page>
      <Link to="/ideas" className="mb-6 inline-block text-meta text-ink-2 hover:text-ink">← Ideas</Link>
      <PageHead title={`Compare ${recs.length} ideas`} sub="The same questions, side by side." />
      <div className="overflow-x-auto"><table className="w-full min-w-[720px]">
        <thead><tr><th />{recs.map((r) => <th key={r.summary.id} scope="col" className="px-4 pb-4 text-left align-bottom font-normal" title={r.summary.id}><Link to={`/ideas/${r.summary.id}`} className="serif text-lead hover:underline">{r.summary.title}</Link></th>)}</tr></thead>
        <tbody>
          {row("Panel says", (r) => r.summary.action ? STATUS[r.summary.action] : "")}
          {row("Strength", (r) => <><Bar60 score={r.summary.score} />{r.summary.score === top && <div className="mt-1 text-meta text-ink-2">Strongest here</div>}</>)}
          {row("The idea", (r) => <p className="text-ink-2">{r.summary.thesis}</p>)}
          {row("Case against", (r) => { const o = r.objections.find((x) => x.status === "open"); return o ? <><div className={`mb-1 text-meta ${o.severity >= 70 ? "text-alert" : "text-ink-2"}`}>{o.severity >= 70 ? "Serious" : "Moderate"} objection</div><p>{humanize(o.headline)}</p></> : <span className="text-ink-2">None open.</span>; })}
          {row("Cheapest check", (r) => <><p>{r.first_check?.smallest_commitment ?? "Not defined yet."}</p><p className="mt-1 text-meta text-ink-2">{r.readiness.enough ? "Defined well enough to run." : "Not yet defined well enough to run."}</p></>)}
          {row("Ambition", (r) => <span className="text-ink-2">{r.summary.cell ? CELLS[r.summary.cell] : ""}</span>)}
          {row("Evidence", (r) => <span className="text-ink-2">{r.evidence.filter((c) => c.kind === "source").length} sourced, {r.evidence.filter((c) => c.kind === "estimate").length} estimated</span>)}
        </tbody>
      </table></div>
    </Page>
  );
}
