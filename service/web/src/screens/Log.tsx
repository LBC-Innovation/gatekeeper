import { Link } from "react-router";
import { useLog } from "../api/hooks";
import { fmtDate, humanize, OUTCOME } from "../lib/text";
import { Empty, ErrorNote, Loading, Page, PageHead } from "../ui/primitives";

const SECTION: Record<string, string> = { weights: "Weights", taste: "Taste", strategy: "Strategy and watch list", capabilities: "Capabilities", rules: "Rules", profile: "Profile", bench: "Who plays" };

export default function Log() {
  const q = useLog();
  if (q.isLoading) return <Page narrow><Loading rows={8} /></Page>;
  if (q.error) return <Page narrow><ErrorNote error={q.error} retry={() => q.refetch()} /></Page>;
  const { decisions, config } = q.data!;
  return (
    <Page narrow>
      <PageHead title="Log" sub="Every decision, newest first. A default that ran because nobody decided is never shown as a decision." />
      {decisions.length === 0 ? <Empty title="No decisions yet" /> : (
        <ol>{decisions.map((d) => {
          const def = d.actor === "default";
          return (
            <li key={d.id} title={d.idea_id} className="grid gap-x-6 gap-y-1 border-t border-rule py-4 md:grid-cols-[120px_1fr]">
              <span className="text-meta text-ink-2 tnum">{fmtDate(d.at)}</span>
              <div>
                <div className="text-[16px]"><Link to={`/ideas/${d.idea_id}`} className="hover:underline">{d.title}</Link></div>
                <div className={`mt-1 ${def ? "italic text-ink-2" : ""}`}>
                  <span className={`font-semibold not-italic ${def ? "text-ink-2" : d.action === "promote" ? "text-positive" : ""}`}>{OUTCOME[d.action] ?? d.action}{def ? " automatically" : ""}</span>
                  {!def && <span className="text-ink-2"> by {d.actor === "human" ? "you" : d.actor}{d.via ? `, in ${d.via === "web" ? "the web app" : d.via === "claude" ? "Claude" : d.via}` : ""}</span>}.{" "}
                  <span className="text-ink-2">{def ? "Nobody decided, so the default ran." : humanize(d.reason)}</span>
                </div>
              </div>
            </li>
          );
        })}</ol>
      )}
      <section className="mt-16"><h2 className="serif mb-2 text-lead">Settings changes</h2>
        <ol>{config.map((c) => <li key={c.id} className="grid gap-x-6 border-t border-rule py-4 md:grid-cols-[120px_1fr]"><span className="text-meta text-ink-2 tnum">{fmtDate(c.at)}</span><div><b className="font-semibold">{SECTION[c.section] ?? c.section}</b> <span className="text-ink-2">by {c.actor === "human" ? "you" : c.actor}. {humanize(c.reason)}</span></div></li>)}</ol></section>
    </Page>
  );
}
