# GateKeeper

**An idea-generation, screening and portfolio-management pipeline that runs inside Claude.** Scouts look outward for signals, a panel of single-job agents argues over what they find, and you get a short queue of decisions with the evidence already assembled. You decide. GateKeeper never does.

It is a Claude Code plugin: one install brings the ledger connector, twelve agents, the skills and a local web dashboard.

---

## Get started (about five minutes, then a forty-five minute interview)

You do not need to run any commands yourself. Your Claude can install GateKeeper and start the interview for you.

### 1. Copy this prompt into Claude Code

> Install GateKeeper from https://github.com/LBC-Innovation/gatekeeper. Add that repository as a plugin marketplace, install the `gatekeeper` plugin from it, and tell me exactly what I need to do to restart or reload so it takes effect. If anything it needs is missing (it requires either `uv` or Python 3.10 or newer), tell me how to install it.

### 2. Reload, then copy this prompt to start the main interview

Once Claude says the plugin is installed, restart Claude Code (or run `/reload-plugins`), open a new session, and paste:

> Run the gatekeeper-setup interview.

That starts the seven-step setup. It reads your company's public record first, then asks only what it cannot read. It can stop and resume at any step. A new session will also offer to start it for you until setup is finished.

### Prefer to type it yourself?

```
/plugin marketplace add LBC-Innovation/gatekeeper
/plugin install gatekeeper@gatekeeper
```

Then reload and say **"Run the gatekeeper-setup interview."**

### What to expect

- **Requirements:** Claude Code (terminal, desktop app Code tab, or IDE), and either [`uv`](https://docs.astral.sh/uv/) (`brew install uv`) or Python 3.10+. The first launch builds a private Python environment in `~/.gatekeeper/` (seconds with `uv`, about a minute without).
- **Your data stays on your machine.** The ledger, briefs, backups and the `inbox/` folder live in `~/Gatekeeper/` (set `GATEKEEPER_HOME` to move it). Plugin updates never touch it.
- **Approvals:** until you allow the connector, Claude asks before each GateKeeper tool call. Setup offers to add `mcp__plugin_gatekeeper_gatekeeper` to your allowed permissions.
- **Update later:** `/plugin marketplace update gatekeeper`.

### The seven steps of the interview

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

## What it is for

Most organizations do not lack ideas. They lack a disciplined way to find the right ones, screen the rest out early and cheaply, and keep a balanced set of bets. GateKeeper is that discipline, run by agents and kept honest by code.

An idea pipeline is a **funnel**: you generate more ideas than you will ever launch, and a series of screens removes the unattractive ones so that the ones that come out the far end have the highest probability and the highest impact. GateKeeper runs that funnel for you every day or week and hands you only the decisions that need a person.

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

Innovation varies along two axes: how new the **technology** is and how new the **market** is. GateKeeper places every idea in one of three cells (the "ambition cell") and manages the mix:

| Cell | Definition | Character |
| --- | --- | --- |
| **Core** (incremental) | Existing customers, existing offerings. Next-version features, process improvements the customer may never notice | Plannable: you can estimate it on a Gantt chart |
| **Adjacent** | One of the two is new: a technology you already do well applied to a new market, or a new technology for the market you know. A stretch, but a bounded one | Moderate risk, moderate reward |
| **Transformational** (radical) | Both are new: a new-to-the-world technology reaching a new-to-the-world market | Highest uncertainty and unusual outside startups, but the source of step changes |

A portfolio should not be all one thing. If you hold too many high-risk, high-payoff projects, you hold some on the launch pad until the balance is right. The default target mix is **60% core, 30% adjacent, 10% transformational** (you set your own in step 3), and the **Steward** agent watches it. One queue slot is always reserved for the best transformational idea, ranked on the panel's score alone, so that your past preferences cannot crowd out exploration.

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
