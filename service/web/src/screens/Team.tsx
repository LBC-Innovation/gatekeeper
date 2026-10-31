import { useState, type ReactNode } from "react";
import { useAgents, useConfig } from "../api/hooks";
import type { AgentProfile } from "../api/types";
import { AgentDialog } from "../components/AgentDialog";
import { Button, ErrorNote, Loading, Page, PageHead } from "../ui/primitives";

const STAGES: { key: AgentProfile["stage"]; title: string; blurb: string }[] = [
  { key: "source", title: "Finding ideas", blurb: "From the outside world to a list of candidate ideas." },
  { key: "judge", title: "Judging them", blurb: "Four reviewers. In round 1 none of them sees the others' work." },
  { key: "close", title: "Telling you", blurb: "Ranking, then a short brief." },
  { key: "learn", title: "Learning from you", blurb: "Once a week." },
];

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex shrink-0 flex-col items-center justify-center text-ink-2 md:px-1" aria-hidden>
      <svg width="28" height="20" viewBox="0 0 28 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="rotate-90 md:rotate-0"><path d="M2 10h22M17 3l7 7-7 7" /></svg>
      {label && <span className="mt-0.5 hidden max-w-[84px] text-center text-[13px] leading-4 md:block">{label}</span>}
    </div>
  );
}

function Node({ a, caption, onOpen }: { a: AgentProfile; caption: ReactNode; onOpen: (id: string) => void }) {
  return (
    <button onClick={() => onOpen(a.id)} aria-label={`${a.name}: read its instructions`} className="group flex w-[148px] shrink-0 flex-col items-center text-center">
      <img src={a.avatar} alt="" width={84} height={84} className="h-[84px] w-[84px] rounded-full transition-transform group-hover:scale-105" />
      <span className="mt-2 font-semibold group-hover:underline">{a.name}</span>
      <span className="text-meta text-ink-2">{caption}</span>
    </button>
  );
}

function You() {
  return (
    <div className="flex w-[148px] shrink-0 flex-col items-center text-center">
      <span className="flex h-[84px] w-[84px] items-center justify-center rounded-full border-[3px] border-accent bg-sunken text-accent" aria-hidden>
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" /></svg>
      </span>
      <span className="mt-2 font-semibold">You</span>
      <span className="text-meta text-ink-2">Decide, with a reason</span>
    </div>
  );
}

function Pipeline({ agents, open }: { agents: AgentProfile[]; open: (id: string) => void }) {
  const cfg = useConfig();
  const r = cfg.data?.rules;
  const by = Object.fromEntries(agents.map((a) => [a.id, a]));
  const n = (k: string, d: number) => (r?.[k] ?? d);
  const gate = Math.round(n("analyst_gate", 0.3) * 100);
  return (
    <section aria-label="How an idea travels">
      <div className="rounded-lg border border-rule bg-surface p-5 md:p-8">
        <h3 className="mb-4 text-meta font-semibold text-ink-2">1. Finding ideas</h3>
        <div className="flex flex-col items-center gap-2 md:flex-row md:items-start md:justify-between">
          <Node a={by.scout} onOpen={open} caption={`Up to ${n("signals_per_sensor", 5)} signals per area`} /><Arrow />
          <Node a={by.curator} onOpen={open} caption={`Keeps up to ${n("kept_per_run", 3)} per run`} /><Arrow />
          <Node a={by.framer} onOpen={open} caption="Writes each one up as a problem" /><Arrow />
          <Node a={by.inventor} onOpen={open} caption={`Up to ${n("candidates_per_problem", 6)} ideas per problem`} />
        </div>

        <div className="my-6 flex items-center gap-3 text-meta text-ink-2" aria-hidden>
          <span className="h-px flex-1 bg-rule" /><span>The ideas go to the panel</span><span className="h-px flex-1 bg-rule" />
        </div>

        <h3 className="mb-4 text-meta font-semibold text-ink-2">2. Judging them</h3>
        <div className="flex flex-col items-center gap-2 md:flex-row md:items-start md:justify-center md:gap-4">
          <Node a={by.analyst} onOpen={open} caption={`First gate: under ${gate} is parked`} /><Arrow />
          <div className="rounded-lg border border-dashed border-rule-strong p-4">
            <p className="mb-3 text-center text-meta text-ink-2">Full panel: up to {n("panel_per_run", 5)} ideas per run</p>
            <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-start">
              <Node a={by.registrar} onOpen={open} caption="Is the check ready?" />
              <Node a={by.steward} onOpen={open} caption="What does it do to the book?" />
              <Node a={by.redteam} onOpen={open} caption="What would sink it?" />
            </div>
          </div>
        </div>

        <div className="my-6 flex items-center gap-3 text-meta text-ink-2" aria-hidden>
          <span className="h-px flex-1 bg-rule" /><span>Scores and objections go to the Arbiter</span><span className="h-px flex-1 bg-rule" />
        </div>

        <h3 className="mb-4 text-meta font-semibold text-ink-2">3. Ranking, and telling you</h3>
        <div className="flex flex-col items-center gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-col items-center gap-2 md:flex-row md:items-start">
            <Node a={by.arbiter} onOpen={open} caption="Ranks the board and explains it" /><Arrow />
            <Node a={by.herald} onOpen={open} caption="Writes the daily brief" /><Arrow />
            <You />
          </div>
          <div className="flex flex-col items-center gap-3 border-t border-rule pt-6 lg:max-w-[440px] lg:flex-row lg:items-start lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
            <Node a={by.calibrator} onOpen={open} caption="Weekly, from your decisions" />
            <p className="text-center text-meta text-ink-2 lg:pt-3 lg:text-left">Every week the Calibrator compares the panel's advice with what you decided, and suggests changes to the weights and rules. You accept or reject each one.</p>
          </div>
        </div>
      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-3">
        {[
          ["From the world", "Scouts search the web across seven areas of change, using the search terms in your watch list."],
          ["From your own data", "Three of those areas can also read exports you drop into the inbox folder: support tickets, sales notes, anything that shows where work gets stuck."],
          ["From you", "Your own ideas skip the panel. They go straight to the board, unscored, and are never parked automatically."],
        ].map(([t, d]) => <div key={t}><h3 className="serif text-lead">{t}</h3><p className="mt-1 text-ink-2">{d}</p></div>)}
      </div>
    </section>
  );
}

function Profile({ a, open }: { a: AgentProfile; open: (id: string) => void }) {
  return (
    <li className="flex flex-col gap-5 border-t border-rule py-7 sm:flex-row">
      <button onClick={() => open(a.id)} aria-label={`${a.name}: read its instructions`} className="shrink-0 self-start">
        <img src={a.avatar} alt="" width={104} height={104} className="h-[104px] w-[104px] rounded-full" />
      </button>
      <div className="min-w-0 flex-1">
        <h3 className="text-title leading-tight">{a.name} <span className="text-lead font-normal text-ink-2">{a.epithet}</span></h3>
        <p className="measure mt-2">{a.bio}</p>
        <p className="mt-3 text-meta text-ink-2">
          {a.schedule}. {a.can_sit_out ? "Can be benched in setup." : "Always plays."} {a.model ? `Runs on ${a.model[0].toUpperCase() + a.model.slice(1)}.` : ""} {a.can_search_web ? "Can search the web." : ""}
        </p>
        <Button className="mt-4" onClick={() => open(a.id)}>Read its instructions</Button>
      </div>
    </li>
  );
}

export default function Team() {
  const q = useAgents();
  const [open, setOpen] = useState<string | null>(null);
  if (q.isLoading) return <Page><Loading rows={8} /></Page>;
  if (q.error) return <Page><ErrorNote error={q.error} retry={() => q.refetch()} /></Page>;
  const agents = q.data!.agents;
  return (
    <Page>
      <PageHead title="The team" sub="Eleven agents, each with one job. They do the reading, sorting and arguing. Only you decide. Click any face to read exactly what that agent was told to do." />
      <Pipeline agents={agents} open={setOpen} />
      <h2 className="mb-1 mt-20 text-display">Who they are</h2>
      <p className="measure mb-6 text-ink-2">Each agent is a short instruction file. The bios below summarise the file's description of who the agent is; the button opens the whole thing.</p>
      {STAGES.map((s) => (
        <section key={s.key} className="mb-10">
          <h3 className="mb-0 text-meta font-semibold text-ink-2">{s.title}<span className="font-normal"> · {s.blurb}</span></h3>
          <ul>{agents.filter((a) => a.stage === s.key).map((a) => <Profile key={a.id} a={a} open={setOpen} />)}</ul>
        </section>
      ))}
      {open && <AgentDialog id={open} onClose={() => setOpen(null)} />}
    </Page>
  );
}
