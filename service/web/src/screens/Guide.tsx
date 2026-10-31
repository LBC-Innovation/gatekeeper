import { Link } from "react-router";
import { Page, PageHead } from "../ui/primitives";

const Code = ({ children }: { children: string }) => <code className="rounded bg-sunken px-1.5 py-0.5 font-mono text-[13px]">{children}</code>;
const Block = ({ children }: { children: string }) => <pre className="my-4 overflow-x-auto whitespace-pre-wrap rounded bg-sunken px-4 py-3 font-mono text-[13px]">{children}</pre>;
const SCHEDULED_PROMPT = "Run the gatekeeper-run skill. This is a scheduled run, so start it with trigger scheduled. Do not ask me anything or wait for me: if a step fails, note it, carry on with the rest, and finish the run. End with the brief.";
const H = ({ id, children }: { id: string; children: string }) => <h2 id={id} className="text-title mb-3 mt-16 scroll-mt-24 first:mt-0">{children}</h2>;
const P = ({ children }: { children: React.ReactNode }) => <p className="measure my-3">{children}</p>;
const Table = ({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) => (
  <div className="my-4 overflow-x-auto">
    <table className="w-full min-w-[520px] border-collapse">
      <thead><tr>{head.map((h) => <th key={h} className="border-b border-rule-strong px-3 py-2 text-left text-meta font-semibold text-ink-2">{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={`border-b border-rule px-3 py-3 align-top ${j === 0 ? "whitespace-nowrap font-semibold" : ""}`}>{c}</td>)}</tr>)}</tbody>
    </table>
  </div>
);

const SECTIONS = [
  ["what", "What it is"], ["day", "Your day with it"], ["decisions", "The four decisions"], ["numbers", "Reading the numbers"], ["screens", "The screens"],
  ["claude", "Using it from Claude"], ["schedule", "Running it on a schedule"], ["connector", "The connector"], ["files", "Where things live"], ["site", "Running the website"], ["habits", "Habits that help"],
] as const;

export default function Guide() {
  return (
    <Page>
      <PageHead title="How it works" sub="A short guide to using Gatekeeper day to day." />
      <div className="grid gap-12 lg:grid-cols-[200px_1fr]">
        <nav aria-label="On this page" className="hidden self-start lg:sticky lg:top-24 lg:block">
          <ul className="space-y-1">{SECTIONS.map(([id, label]) => <li key={id}><a href={`#${id}`} className="block py-1 text-ink-2 hover:text-ink">{label}</a></li>)}</ul>
        </nav>

        <article className="min-w-0 max-w-[760px]">
          <H id="what">What it is</H>
          <P>Gatekeeper looks for new opportunities for your business and brings you the few that are worth a decision. A team of eleven agents does the reading, sorting and arguing. You make every decision; the agents only recommend. The <Link to="/team" className="text-accent underline underline-offset-2">Team</Link> page shows who does what.</P>
          <P>A run takes around fifteen minutes. It can happen on a schedule or whenever you ask. When it finishes, whatever needs you is waiting on <Link to="/today" className="text-accent underline underline-offset-2">Today</Link>.</P>

          <H id="day">Your day with it</H>
          <ol className="measure my-3 list-decimal space-y-3 pl-6">
            <li>Open <b>Today</b>. The heading tells you how many decisions and serious objections are waiting.</li>
            <li>Pick one. Read the panel's one-line advice, then the case for and the case against. Each is a single sentence, with the full argument a click away.</li>
            <li>Press one of the four buttons. A sheet asks why. Tap a reason or write your own; it needs a few words.</li>
            <li>You have five seconds to undo. After that the decision is written to the ledger for good.</li>
          </ol>
          <P>If you do nothing, the line under each item says what will happen and when, for example “updated to Parked on Wed, Nov 4”. Each item has a date, a week after it joined your queue by default. On that date its status is updated for you: usually to Parked, or to Find out first when the panel asked for more evidence. Nothing is funded or killed this way. The log records the update as automatic, never as your decision, and you can still decide on the idea afterward.</P>

          <H id="decisions">The four decisions</H>
          <Table head={["Button", "What it means"]} rows={[
            ["Fund the check", "Pay for the smallest piece of work that would test the idea, with an owner. It does not fund the whole idea."],
            ["Find out first", "Ask the panel to settle one question before you decide. The answer comes back to your queue."],
            ["Park", "Set it aside for now."],
            ["Kill", "Close it. Your reason teaches the panel what you turn down."],
          ]} />

          <H id="numbers">Reading the numbers</H>
          <Table head={["Term", "What it means"]} rows={[
            ["Strength", "A score from 0 to 100 that blends two reviewers: Strategy (does it fit what we are trying to do, and can we build it) and Portfolio (what it does to the mix of work you already have)."],
            ["Fund line, park line", "Strength of 65 or more is a strong idea. Under 45 the panel suggests parking. In between is your judgment. Both lines are in Settings."],
            ["Serious objection", "Red Team argues against every idea without knowing whose it is. An objection rated 70 or more always reaches you, however high the score."],
            ["Readiness", "How many of 18 points the first check has earned. It is not part of strength, but a strong idea with a vaguely defined check is marked Find out first."],
            ["Split panel", "Strategy and Portfolio still disagree after a second round."],
          ]} />

          <H id="screens">The screens</H>
          <ul className="measure my-3 space-y-3">
            <li><b>Today.</b> What is waiting on you, with a date for each.</li>
            <li><b>Ideas.</b> Everything on the board, ranked, with the fund and park lines marked. Tick <i>Compare</i> to set a few side by side. Turn on <i>My order</i> to drag ideas into the order you would fund them; where you differ from the panel is what the Calibrator learns from.</li>
            <li><b>An idea.</b> Tabs for the case, how each reviewer scored it, the objections, the evidence behind every figure, where it came from, and its history.</li>
            <li><b>Log.</b> Every decision, yours and automatic, with the reason.</li>
            <li><b>Team.</b> Who the agents are, and how an idea passes between them.</li>
            <li><b>The gear menu.</b> Portfolio balance, Settings (weights, taste, the watch list), Pipeline runs, and Signals.</li>
          </ul>

          <H id="claude">Using it from Claude</H>
          <P>Claude reads the same ledger. Anything you can do here you can do in chat, and a few things only work in chat. These skills start when you say something like the phrase on the left.</P>
          <Table head={["Skill", "You say", "What it does"]} rows={[
            [<Code key="s">gatekeeper-setup</Code>, "“Set up Gatekeeper”", "A seven-step interview. It reads your company's public record first and asks only what it cannot read: your directives, product lines, work in flight, who plays, and your scoring weights. Run it once, and again if strategy changes."],
            [<Code key="r">gatekeeper-run</Code>, "“Run Gatekeeper”, “sweep now”", "One full pass: scout, curate, frame, invent, panel, rank, brief. This is also what a daily schedule runs."],
            [<Code key="v">gatekeeper-review</Code>, "“What needs me?”, “park 0042 because…”", "Look at the board, open an idea, decide, rank, answer an objection, ask for evidence, change a weight, accept a suggestion from the Calibrator."],
            [<Code key="d">gatekeeper-digest</Code>, "“Write this week's digest”", "A weekly email you can reply to in order to decide. Still a test."],
          ]} />
          <P>Only chat can do these: change your strategy or capabilities (Claude drafts it, shows what would move, and saves it with your reason); change a rule's threshold; ask <i>why</i> the panel scored something the way it did; ask Claude to argue the other side of an objection; and add an idea of your own, which goes straight to the board.</P>

          <H id="schedule">Running it on a schedule</H>
          <P>A scheduled task in the Claude desktop app runs Gatekeeper for you, so new ideas are waiting when you sit down. Set it up once, after the setup interview is done.</P>
          <ol className="measure my-3 list-decimal space-y-3 pl-6">
            <li>Open the Claude desktop app and go to the <b>Code</b> tab.</li>
            <li>In the left sidebar, click <b>Scheduled</b>. The <i>Scheduled tasks</i> page opens.</li>
            <li>Click <b>New task</b>. If it asks where the task should run, choose this computer (local), not the cloud: the ledger lives on this computer.</li>
            <li>For the folder, pick your Gatekeeper folder: the one that holds <Code>CLAUDE.md</Code> and <Code>data/</Code>.</li>
            <li>Name it <i>Gatekeeper run</i> and paste the prompt below as its instructions.</li>
            <li>Pick a schedule. <b>Weekly</b>, early Monday, suits most people. <b>Daily</b>, before you start work, suits a busy market. More often than daily adds cost, not insight.</li>
            <li>Save it, then open the task and run it once now, while you watch. Each time Claude asks for permission, choose <b>Always allow</b>. Later runs then go through without stopping to ask.</li>
            <li>Keep the computer from sleeping at the scheduled time: turn on Claude's keep-awake setting if your version has one, or set your Mac not to sleep while plugged in.</li>
          </ol>
          <P>The prompt to paste:</P>
          <Block>{SCHEDULED_PROMPT}</Block>
          <P>A run needs the Claude app open and the computer awake. If the computer was asleep at the scheduled time, the run starts once when it wakes. When a run finishes, it appears under <b>Pipeline runs</b> in the gear menu, and anything that needs you is on <b>Today</b>. The task's history in Claude ends with the brief for that run. If a run failed, that history says why.</P>
          <P>To stop or change it, click <b>Scheduled</b> in the sidebar, open the <i>Gatekeeper run</i> task under <b>Yours</b>, and edit or delete it. A run you start by hand (“Run Gatekeeper”) works the same way and does not affect the schedule.</P>

          <H id="connector">The connector</H>
          <P>Claude talks to Gatekeeper through an <b>MCP connector</b>. MCP is a standard way of giving Claude a set of tools; here they read the board, file a review or record a decision.</P>
          <ul className="measure my-3 list-disc space-y-3 pl-6">
            <li><b>One door.</b> Every write goes through the connector, and it checks each one. A figure needs a source or a labelled estimate. A decision needs a reason. Red Team cannot see who sponsored an idea. If a write breaks a rule it is refused with a message that says what to fix.</li>
            <li><b>Two surfaces.</b> The <i>person</i> surface has every tool, including <Code>decide</Code>. The <i>pipeline</i> surface is what the agents may call, and it has no <Code>decide</Code>, so an agent cannot record a decision even by mistake.</li>
            <li><b>Same rules everywhere.</b> This website uses the same rules, so a decision made here and one made in chat are checked the same way.</li>
            <li><b>Hands off the files.</b> Do not edit <Code>data/</Code> or <Code>context/</Code> by hand. The ledger is append-only on purpose.</li>
            <li><b>If Claude says the tools are missing,</b> run <Code>scripts/install.sh</Code> and restart Claude.</li>
          </ul>

          <H id="files">Where things live</H>
          <Table head={["Folder", "What is in it"]} rows={[
            [<Code key="1">data/</Code>, "The ledger: every signal, idea, review, objection and decision."],
            [<Code key="2">context/</Code>, "The business context the agents read, written out from your setup."],
            [<Code key="3">briefs/</Code>, "The daily briefs, one file per run."],
            [<Code key="4">inbox/</Code>, "Drop exports here for the scouts that read your own data."],
            [<Code key="5">claude-config/</Code>, "The agents and skills as source files. Open any agent on the Team page to read its file. Edits take effect after running scripts/install.sh."],
            [<Code key="6">service/</Code>, "This website, its API and the connector."],
          ]} />

          <H id="site">Running the website</H>
          <P>Start it with <Code>python service/serve.py</Code>. It prints a one-time sign-in link; open it once and the browser stays signed in for 30 days. If you lose the link, <Code>python service/serve.py open</Code> prints a new one. The site only runs on this computer.</P>
          <Table head={["Key", "Does"]} rows={[
            [<Code key="a">j</Code>, "Next item. K goes back."],
            [<Code key="b">1 2 3 4</Code>, "Fund the check, Find out first, Park, Kill."],
            [<Code key="c">a</Code>, "Answer the objection."],
            [<Code key="d">r</Code>, "Ask for evidence."],
            [<Code key="e">Enter</Code>, "Open the idea."],
            [<Code key="f">⌘K</Code>, "Search ideas or jump to any page."],
          ]} />

          <H id="habits">Habits that help</H>
          <ul className="measure my-3 list-disc space-y-3 pl-6">
            <li>Give real reasons. The Calibrator reads them. “The law is unclear” teaches it more than “no”.</li>
            <li>Use <i>My order</i> now and then. Your ordering against the panel's is the best signal it gets.</li>
            <li>Answer serious objections, even if the answer is “I accept this risk”.</li>
            <li>Treat an automatic park as a missed decision, not a decision. Check the log now and then.</li>
          </ul>
        </article>
      </div>
    </Page>
  );
}
