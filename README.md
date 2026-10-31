# GateKeeper

## A product of LBCInnovation.com

## Quick start

Scouts look outward for signals, a panel of single-job agents argues over what they find, and you get a short queue of decisions with the evidence already assembled. You decide. GateKeeper never does.

**Paste this into Claude Code** and it installs GateKeeper for you:

> Install GateKeeper from https://github.com/LBC-Innovation/gatekeeper. Add that repository as a plugin marketplace, install the `gatekeeper` plugin from it, and tell me exactly what I need to do to restart or reload so it takes effect. If anything it needs is missing (it requires either `uv` or Python 3.10 or newer), tell me how to install it.

Then reload, open a new session, and paste the line that starts the main interview:

> Run the gatekeeper-setup interview.

Full setup details, requirements and manual commands are at the [bottom of this page](#install-and-set-up).

---

## Contents

1. [What it is and what it is for](#what-it-is-and-what-it-is-for)
2. [Key terms](#key-terms)
3. [Why it is built this way](#why-it-is-built-this-way)
   - [Ideas are cheap; the system around them is the work](#ideas-are-cheap-the-system-around-them-is-the-work)
   - [Three barriers that keep good ideas out](#three-barriers-that-keep-good-ideas-out)
   - [The dimensions of innovation](#the-dimensions-of-innovation-core-adjacent-transformational)
   - [How breakthroughs happen](#how-breakthroughs-happen)
   - [Screening: stage gates](#screening-stage-gates-kept-rigorous-and-flexible)
   - [Where AI fits, and where it must not](#where-ai-fits-and-where-it-must-not)
4. [How it works](#how-it-works)
5. [Using it](#using-it)
6. [What is enforced in code](#what-is-enforced-in-code-not-in-prompts)
7. [Not built yet](#not-built-yet)
8. [Install and set up](#install-and-set-up)
9. [For developers](#for-developers)

---

## What it is and what it is for

GateKeeper is an **idea-generation, screening and portfolio-management pipeline** that runs inside Claude. It is a Claude Code plugin: one install brings the ledger connector, twelve agents, the skills and a local web dashboard.

Most organizations do not lack ideas. They lack a disciplined way to find the right ones, screen the rest out early and cheaply, and keep a balanced set of bets. GateKeeper is that discipline, run by agents and kept honest by code.

An idea pipeline is a **funnel**: you generate more ideas than you will ever launch, and a series of screens removes the unattractive ones so that the ones that come out the far end have the highest probability and the highest impact. GateKeeper runs that funnel for you every day or week and hands you only the decisions that need a person.

## Key terms

GateKeeper has its own vocabulary. This table says what each word means here and the idea in innovation management it comes from. Read it top to bottom once: the terms follow the order an idea travels.

**An idea's path:** signal → problem → candidate → reviewed idea → your decision.

### The funnel, in order

| Term | What it means in GateKeeper | The idea behind it |
| --- | --- | --- |
| **Signal** | A cited observation that something in the world is changing, filed by a Scout. It carries a title, a source URL, the date it was retrieved and a quoted excerpt. A signal is **not an idea** and not yet a problem: it is raw evidence of change, the very start of the funnel | Innovation starts from a change, not from a brainstorm. The *sources of innovation* (unexpected occurrences, incongruities, process needs, industry change, demographics, perception shifts, new knowledge) are where opportunity shows up first. Looking outward for change is how a company avoids listening only to its current market |
| **Opportunity area** (also **sensor**) | One of seven places a Scout looks. Each area has its own search terms | The seven *sources of innovation*, one Scout per source, so no single viewpoint dominates |
| **Watch list** | The public search terms you approve for each external area. Internal areas read your own exports from `inbox/` | Observation beats opinion: external areas use real-world evidence, internal areas use what your own data actually shows, not what people say in a survey |
| **Novelty** | A 0-to-1 score for how new a signal is **to your ledger**, not to the world. Below the *novelty floor* (0.35 by default) it is dropped | The funnel must eliminate "old things wearing new clothes". Attention is the scarce resource, so repeats and near-duplicates are filtered out |
| **Kept / dropped** | The Curator's verdict on every signal, with a one-line reason. A drop is a decision too | The first screen. Most inputs should not survive, and the reasons are recorded so the filter can be improved |
| **Problem** | A signal turned into a stated problem: who has it, why it matters now, and what it is not. Written by the Framer | Define before you develop. A *technology broker* works with a specific problem in mind, which is what lets recombination aim at something. It also guards against *user myopia*, where users propose solutions rather than state needs |
| **Candidate** (also **idea**) | A proposed solution to one problem, drafted by the Inventor. Up to six per problem, each different in mechanism, each tagged with the technique that produced it | The *develop* half of the Double Diamond: diverge again, widen the options before choosing |
| **Technique** | One of four ways the Inventor generates candidates: forced relationship, compare and contrast, forced solutions, compounding | Structured idea generation beats unstructured brainstorming. Several of these deliberately carry a mechanism across from an unrelated field, because breakthroughs recombine knowledge from different domains |
| **Four P's** | Every idea is tagged **product, process, position** (who you sell to, how you are seen) or **paradigm** (what business you are in) | Innovation is not only products. Process and business-model innovation are first-class, so GateKeeper does not default to "a new product" |
| **First check** | The smallest commitment that would retire the biggest uncertainty about an idea | *Fail cheap, fail quick, learn fast.* Invest incrementally, and learn before you spend. Every candidate arrives with one |

### Judging and deciding

| Term | What it means in GateKeeper | The idea behind it |
| --- | --- | --- |
| **Ambition cell** | Where an idea sits on the innovation map: **core** (existing customers, existing offerings), **adjacent** (one of those is new), **transformational** (both are new) | The *dimensions of innovation*: incremental versus adjacent versus radical, defined by how new the technology and the market are. See [the dimensions](#the-dimensions-of-innovation-core-adjacent-transformational) |
| **Mix target** | The share of your portfolio you want in each cell. Default: 60% core, 30% adjacent, 10% transformational (tolerance 5 points) | A portfolio, not a pile of look-alike projects. Balance risk and reward across the set |
| **Exploratory floor** | The minimum number of live transformational items you want to keep alive (default 2). The Steward raises an alarm below it | Protects the long bets from being crowded out by safe, incremental work |
| **Gate** | A checkpoint where an idea gets a go, kill, hold or recycle answer. The **Analyst gate** is the first: a score below 0.30 parks the idea | The *stage-gate* process: a disciplined, cross-functional review at each stage, fast and cheap early and stricter later |
| **Readiness** | How ready an idea is for **its next gate**, scored by the Registrar on six dimensions. It is not a verdict on the idea's merit. Low readiness means "find out first", not "bad idea" | Evidence requirements grow gate by gate. Demanding a launch plan from an idea framed this morning would kill every idea |
| **Panel** | The agents that judge an idea: Analyst, Steward, Registrar and Red Team. Each has one job and none can see the others' first-round work | A multidisciplinary team in which each function judges from its own seat. Independent first judgments avoid anchoring on the loudest voice |
| **Round 1 / Round 2** | Round 1 is independent and blind. Round 2 happens only if the panel is split or Red Team raised a serious objection; reviewers see the others' reasons, anonymized, and may revise once, giving a reason | Disagreement is information. Where one reviewer sees a five and another a one, that is the most valuable conversation. A large spread means gather more information |
| **Objection** and **severity** | The Red Team's strongest argument against an idea, with a 0-to-1 severity. At 0.70 or more, it puts the idea in your queue no matter its score | Ask "what is wrong with this?" rather than "do you like it?" Criticism is kept beside the score and never averaged away |
| **Score, band, spread** | **Score** blends the Analyst and Steward. **Band** is the Red Team's confidence band. **Spread** is how far apart the voters were | Keep weighting coarse; precision beyond what the evidence supports is false comfort |
| **Action** | What the system recommends for an idea: `PROMOTE`, `NEED_EVIDENCE`, `PARK`, `CONSIDER`, `CONTESTED`, `REVIEW_OBJECTION` | The gate outcomes (go, hold, recycle, kill), made explicit so nothing is decided silently |
| **Board / queue / brief** | The **board** is every ranked idea. The **queue** is the at most three that need *you*. The **brief** is the short written summary of a run | Attention is the scarce resource when supply of ideas is unlimited, so filtering is the capability that matters |
| **Decision** | Your answer on a queued idea: `promote`, `kill`, `park`, `need_evidence` or `keep`, with a one-line reason | Judgement stays with the accountable person, and the reason is how the system learns what you value |
| **Default** | What happens to a queued item you do not decide by its date (seven days). Always conservative (park or need evidence) and recorded as a default, never as your decision | Guards against ideas drifting forward by inertia, and against *escalation bias* |
| **Kill trigger** | Two automatic kill recommendations: **stall** (idle far longer than the usual gap between events) and **drift** (the directive it served has been retired). A kill recommendation defaults to kill; keeping it needs a written reason | Do not keep funding what no longer fits. Make stopping a normal, recorded event rather than a quiet failure |

### Your setup and the ledger

| Term | What it means in GateKeeper | The idea behind it |
| --- | --- | --- |
| **Directive** | A funded strategic priority you confirm in setup, with a horizon | *Fit with strategy* is the first screening question at every gate |
| **Portfolio line** / **in flight** | A product or service you sell today / work already funded and under way | You cannot judge cannibalization or balance without knowing the real book of business |
| **Capability** | What your organization can do, with its maturity, plus what you could acquire within a year | A *core competence* is an asset, but one applied to every decision hardens into a *core rigidity*. The panel checks fit **and** flags where a capability must be extended |
| **Exemplar** | A past idea of yours with its known outcome: funded and glad, funded and regretted, killed, killed and regretted | Calibration against decisions you have already made, so the panel's taste can be checked against your judgement |
| **Calibration** | Comparing the panel's ranking with your decisions and your own ordering, then **proposing** changes to weights or rules. Nothing changes unless you accept | A learning system, with the person as final authority |
| **Protected idea** | An idea you submit yourself. It stays on the board, unscored, and no default action ever applies to it | Prevents the system from quietly parking the sponsor's own conviction |
| **Bench** | An agent you choose to leave out of the run (the Analyst and Registrar always play) | Match the team to the decision; every seat costs time |
| **Claim** | A figure with its evidence attached: either **sourced** (URL, retrieval date, quoted excerpt) or an **estimate** (confidence and basis). A number with neither is rejected | Know what you know versus what you are guessing |
| **Ledger** | The append-only database of everything above. Facts and judgments cannot be edited or deleted after the fact | An auditable record: every number on the board can be reproduced by hand |
| **Run** | One pass of the pipeline, from scouting to the brief | The funnel in motion, on a schedule you choose |

---

## Why it is built this way

### Ideas are cheap; the system around them is the work

Ideas on their own have limited value. They are a dime a dozen, and creativity is rarely the problem. Execution is. Famous failures were often not failures to see the idea but failures to move the stakeholders around it. So GateKeeper does not stop at brainstorming. Every candidate arrives with a **first check**, the smallest commitment that would retire the biggest uncertainty, and a decision queue so an idea either moves or is stopped with a reason on record.

### Three barriers that keep good ideas out

| Barrier | What it is | What GateKeeper does about it |
| --- | --- | --- |
| **Core rigidity** | A core competence applied to every decision hardens into a rigidity. The dark side of core capabilities appears when the pace of change outside exceeds the pace inside | Scouts bring in external knowledge continuously; the panel judges capability fit **and** flags where a capability must be extended |
| **Tyranny of the current market** | Listening only to current customers leaves you stuck in current markets while a new one reaches critical mass | Scouts sweep seven areas, four of them entirely outside the company; internal signals come from observed data in `inbox/`, not from surveys |
| **User myopia** | Users cannot envision technology you have not shown them, and not all users are equal | The Framer states the underlying problem, not a customer's requested solution |

A culture that minimizes these barriers rewards intelligent failure, never confuses process with outcome, and asks "what is wrong with this?" rather than "do you like it?". That last habit is a job: the **Red Team** agent.

### The dimensions of innovation: core, adjacent, transformational

Innovation varies along two axes: how new the **technology** is and how new the **market** is. GateKeeper places every idea in one of three cells (the *ambition cell*) and manages the mix:

| Cell | Definition | Character |
| --- | --- | --- |
| **Core** (incremental) | Existing customers, existing offerings. Next-version features, process improvements the customer may never notice | Plannable: you can estimate it on a Gantt chart |
| **Adjacent** | One of the two is new: a technology you already do well applied to a new market, or a new technology for the market you know. A stretch, but a bounded one | Moderate risk, moderate reward |
| **Transformational** (radical) | Both are new: a new-to-the-world technology reaching a new-to-the-world market | Highest uncertainty and unusual outside startups, but the source of step changes |

A portfolio should not be all one thing. If you hold too many high-risk, high-payoff projects, you hold some on the launch pad until the balance is right. The default target mix is **60% core, 30% adjacent, 10% transformational** (you set your own in setup), and the **Steward** agent watches it. One queue slot is always reserved for the best transformational idea, ranked on the panel's score alone, so that your past preferences cannot crowd out exploration.

Risk and reward travel together along a diagonal: low risk and low reward, moderate and moderate, high and high. Low-risk, high-reward is rare, and high-risk, low-reward is not worth funding unless you need the learning. The panel scores against exactly that.

### How breakthroughs happen

A **breakthrough** changes products, processes or services so dramatically that it transforms markets, and the market, not only the technology, has to accept it. (A *radical* innovation is the close cousin that creates a *new* market; a breakthrough shifts an existing one dramatically. The two are often used interchangeably.)

Three things follow, and they shaped the design:

1. **You cannot schedule one.** Incremental work fits on a Gantt chart. A breakthrough does not: no number of experiments guarantees it. So GateKeeper does not pretend to predict breakthroughs. It keeps cheap options open and makes every bet small and early, in the spirit of *fail cheap, fail quick, learn fast*.
2. **They come from recombination, not from a vacuum.** Breakthroughs usually join knowledge from different domains: Ford's assembly line borrowed from meatpacking, sewing machines and fisheries. The usual advice is "think inside multiple boxes," not outside the box. That is the **Inventor**, which uses four named techniques (forced relationship, compare and contrast, forced solutions, compounding), and it is why the Scouts range across seven distinct areas.
3. **It is as much social as technical.** Breakthroughs are built by communities of people and ideas around a problem, and knowledge grows in value the more it is used. A *technology broker* moves knowledge between domains **in service of a specific problem**; a gatekeeper facilitator moves it for its own sake. GateKeeper makes the problem explicit first (the **Framer**) so recombination has something to aim at, and a panel with distinct roles stands in for the community that stress-tests it.

> The future is already here, it is just unevenly distributed. Your job is to find the part of it being pursued elsewhere and bring it together with what you can do.

### Screening: stage gates, kept rigorous and flexible

Each idea passes through gates where the answer is **go, kill, hold, or recycle** (needs more information). GateKeeper follows the standard disciplined-gate practices:

- Early gates are fast and cheap, based on judgement; evidence requirements **grow gate by gate**. Asking an idea framed this morning for a launch plan would kill every idea, so the **Registrar** scores readiness only for the gate the idea is actually at.
- The classic gate questions: Does it fit strategy? Is the risk-to-reward favorable? Is it technically feasible? Is there a differentiating advantage? Does it match at least one core competence? Is the market attractive? These are the **Analyst's** questions.
- Rate on a 1-to-5 style scale, involve every function, and **use disagreement**. Where one reviewer sees a five and another a one, that is the most valuable conversation. Large spread means gather more information. In GateKeeper, a split panel triggers a structured second round.
- Keep weighting simple. Precision beyond what the evidence supports is false comfort, so there are a few coarse weights, and you change them only with a reason on record.
- Beware **escalation bias**, the pull to push a favorite past a gate it did not clear. Defaults are conservative, and a kill recommendation defaults to kill: keeping the idea takes a written reason.
- A pipeline has two rhythms. The Double Diamond names them: **diverge** to widen options, **converge** to decide, twice over.

| Double Diamond | Diverge or converge | GateKeeper |
| --- | --- | --- |
| Discover | Diverge | Scouts sweep seven areas; Curator removes duplicates and scores novelty |
| Define | Converge | Framer turns a kept signal into a stated problem |
| Develop | Diverge | Inventor drafts up to six candidates per problem, each by a different technique |
| Deliver | Converge | Gate, panel, Arbiter, then at most three decisions for you |

### Where AI fits, and where it must not

AI is genuinely good at three things in this process: **accelerating idea generation** (scouring the world for where ideas are being discussed), **improving evaluation** (weighing ideas against strategy, markets and feasibility), and **automating the repetitive work** (collection, analysis, reporting). It is also easy to lead astray: small changes in an agent's behavior can produce very wrong decisions. So the design splits the labour:

- **Agents supply judgments.** **Code turns judgments into a ranking**, and every number on the board can be reproduced by hand.
- Every figure needs a **claim**: a cited source or a labeled estimate. No claim, no write.
- When supply of ideas is effectively unlimited, **attention is the scarce resource** and filtering becomes the critical capability. So the queue is capped at three open decisions, duplicates are caught, and a novelty floor drops what you already know.
- **Decisions belong to the person.** The system never records one you did not make.

---

## How it works

```
 Scouts (7 areas) ─▶ Curator ─▶ Framer ─▶ Inventor ─▶ Analyst gate ─▶ Panel ─▶ Arbiter ─▶ Herald ─▶ YOU
   find signals     keep few    state the   up to 6      parks the      Registrar   ranks,     writes     promote
                                problem     candidates   weak           Steward     explains   the brief  kill park
                                                                         Red Team                           evidence
```

| Agent | Single job | Votes? |
| --- | --- | --- |
| **Scout** (one per area) | Sweeps one opportunity area for cited, genuinely new signals | no |
| **Curator** | Deduplicates, scores novelty, keeps or drops each signal | no |
| **Framer** | Turns a kept signal into a problem worth solving | no |
| **Inventor** | Drafts divergent candidate solutions with four named techniques | no |
| **Analyst** | Strategic fit and capability match; first gate (below 0.30 is parked) | yes, 0.35 |
| **Steward** | Portfolio fit, mix balance, cannibalization | yes, 0.30 |
| **Registrar** | Is the idea ready for its next gate? Fund the check, or find out first | no, it decides *what to do next* |
| **Red Team** | Strongest case against the idea, blind to who sponsored it | a band, not a score (0.15) |
| **Cartographer** | Checks the idea against your engineering backlog (optional) | no |
| **Arbiter** | Chairs the panel and explains disagreement | no |
| **Herald** | Writes the brief as a decision queue | no |
| **Calibrator** | Weekly: compares the panel with your decisions and *proposes* changes | no |

The seven opportunity areas the Scouts cover come from Drucker's sources of innovation: unexpected occurrences, incongruities, process needs, industry and market change, demographics, perception shifts, and new knowledge. Each idea is also tagged product, process, position or paradigm, so process and business-model ideas are first-class, not an afterthought to products.

The full mechanics (thresholds, the second round, how an open objection forces an idea into your queue) are in [docs/DELIBERATION.md](docs/DELIBERATION.md).

---

## Using it

| When | Say |
| --- | --- |
| Once | "Run the gatekeeper-setup interview." |
| Each pass (daily or weekly) | "Run gatekeeper-run." Or schedule it so it runs without you |
| Any morning | "Show my GateKeeper board." / "What needs me?" |
| To decide | "Promote 0042 because..." — every decision needs a one-line reason; that reason is how the system learns what you value |
| To see everything in a browser | "Start the dashboard." (`gatekeeper-dashboard`) |
| A weekly email you can reply to | "Write this week's digest." (`gatekeeper-digest`) |
| To go back | "Restore a backup." (`gatekeeper-restore`) |

Decisions are `promote`, `kill`, `park`, `need_evidence`, or `keep` (to answer a kill recommendation). Anything you do not decide by its default date executes as a **default**, recorded as a default, never as your decision.

## What is enforced in code, not in prompts

- Every figure needs a sourced claim or a labeled estimate, or the write is rejected.
- Red Team never sees sponsor, origin or source sensor. Panelists never see each other's round-1 work.
- Facts and judgments are append-only: the database blocks updates and deletes.
- Per-run caps, duplicate detection and a novelty floor. A queue limit of three.
- Calibration changes are proposals. Nothing changes without your yes.
- Public web searches are built only from your watch-list terms, never from internal data.

## Not built yet

The S-curve renewal-timing estimator (when to launch the next generation before the current one plateaus), competitive-preemption and window-closed kill triggers, resurrection of killed ideas, and hosted access from a phone.

---

## Install and set up

The [Quick start](#quick-start) prompt at the top does all of this for you. These are the details behind it.

### Requirements

- Claude Code (terminal, desktop app Code tab, or IDE).
- Either [`uv`](https://docs.astral.sh/uv/) (`brew install uv`) or Python 3.10+. The first launch builds a private Python environment in `~/.gatekeeper/` (seconds with `uv`, about a minute without).

### Install by hand

```
/plugin marketplace add LBC-Innovation/gatekeeper
/plugin install gatekeeper@gatekeeper
```

Then restart Claude Code (or run `/reload-plugins`), open a new session, and say **"Run the gatekeeper-setup interview."** A new session will also offer to start it for you until setup is finished.

### What to expect

- **Your data stays on your machine.** The ledger, briefs, backups and the `inbox/` folder live in `~/Gatekeeper/` (set `GATEKEEPER_HOME` to move it). Plugin updates never touch it.
- **Approvals.** Until you allow the connector, Claude asks before each GateKeeper tool call. Setup offers to add `mcp__plugin_gatekeeper_gatekeeper` to your allowed permissions.
- **Optional backlog check.** Set `GATEKEEPER_ADO_DB` to point at an Azure DevOps snapshot. Without it that one feature says it is not connected and everything else works.
- **Update later:** `/plugin marketplace update gatekeeper`.

### The seven steps of the interview

It takes about forty-five minutes, reads your company's public record first, asks only what it cannot read, and can stop and resume at any step.

| Step | What happens |
| --- | --- |
| 1. Read the public record | Claude reads your company's public sources and drafts a profile, with a URL for every fact |
| 2. Confirm and correct | You fix the draft. Correcting beats authoring from a blank page |
| 3. What it cannot read | Strategic directives, what you are hunting for (offerings, processes, business models), what is off limits, your target mix, your watch list |
| 4. What is not public | Current product lines, work already in flight, capabilities, where the portfolio hurts |
| 5. Assemble the team | Which agents play and which sit out |
| 6. Set the weights | A few dials, anchored to decisions you have already made |
| 7. Calibrate | Past ideas you funded and killed, so the panel can be checked against your judgement |

When it is done, say **"Run gatekeeper-run"** to watch the first board fill.

---

## For developers

Run from a checkout instead of the plugin:

```
bash scripts/install.sh            # .venv, agents and skills into .claude/, tests, .mcp.json
claude --plugin-dir .              # or try the plugin from this folder
```

```
.venv/bin/python -m pytest service/tests
.venv/bin/python -m unittest discover -s tests
```

| Path | What it is |
| --- | --- |
| `.claude-plugin/` | Plugin and marketplace manifests |
| `bin/gk` | Launcher: builds the Python environment on first use, then runs the connector, scripts or dashboard |
| `service/` | The engine: ledger, rules, MCP connector, web API and the built web app |
| `claude-config/agents/` | The twelve agents, one job each |
| `claude-config/skills/` | setup, run, review, dashboard, digest, restore |
| `hooks/` | Offers the setup interview in a new session until it is finished |
| `docs/DELIBERATION.md` | How the panel decides, and why |

Author: zhwatts.
