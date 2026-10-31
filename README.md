# Gatekeeper

An idea pipeline that runs inside the Claude desktop app. Scouts find signals every day, a panel of single-job agents deliberates, and you get a short queue of decisions with the evidence already assembled.

Author: zhwatts. MVP built 2026-10-08.

## What is in this folder

```
gatekeeper/
  server/                    the connector: a local MCP server over SQLite
    gatekeeper_server.py     MCP entry point (57 tools)
    gatekeeper/core.py       every rule: fidelity, blinding, caps, gates, defaults, kill triggers
    gatekeeper/deliberation.py   the scoring and ranking math, pure functions
    gatekeeper/schema.sql    the ledger
  claude-config/agents/      eleven agents, one job each
  claude-config/skills/      gatekeeper-setup (interview), gatekeeper-run (daily pass), gatekeeper-review (chat),
  claude-config/settings.json  pre-approves the connector and web tools so scheduled runs do not stall
                             (install.sh copies all three into .claude/, where Claude reads them;
                             edit them in claude-config/ and re-run install.sh)
  docs/DELIBERATION.md       how the panel decides, and why
  tests/                     rule tests and an MCP smoke test
  scripts/install.sh         one-time setup
  scripts/new-instance.sh    clean copy of this folder, installed, 
  inbox/                     drop internal exports here for the internal sensors
  briefs/                    daily briefs, one markdown file per run
  data/                      the ledger (created on first run)
  context/                   generated read-only view of your configuration
```

## Install as a Claude Code plugin

Gatekeeper is a plugin: the connector, the twelve agents and the skills install together. In Claude Code:

```
/plugin marketplace add <owner>/<repo>
/plugin install gatekeeper@gatekeeper
```

Then restart Claude Code (or `/reload-plugins`) and say **set up Gatekeeper**. A new session also offers the setup on its own until it is finished. Or hand a person this repo's link and tell their Claude "install Gatekeeper from <link>".

- **Needs** `uv` (`brew install uv`) or Python 3.10 or newer. The first launch builds a private Python environment in `~/.gatekeeper/` (about a minute without `uv`, seconds with it); it is reused after that.
- **Your data stays yours.** The ledger, briefs, backups and inbox live in `~/Gatekeeper/` (set `GATEKEEPER_HOME` to move it), never inside the plugin, so updates cannot touch them. Sign-in tokens and the environment are in `~/.gatekeeper/`.
- **Approvals.** Claude asks before each Gatekeeper tool call until the connector is allowed; the setup offers to add `mcp__plugin_gatekeeper_gatekeeper` to your allowed permissions.
- **Optional:** `GATEKEEPER_ADO_DB` points the backlog check at an Azure DevOps snapshot. Without it that one feature says it is not connected and everything else works.
- **Update** with `/plugin marketplace update gatekeeper`.

## Run from a checkout instead (development)

```
bash scripts/install.sh            # .venv, agents and skills into .claude/, tests, .mcp.json
bash scripts/install.sh --desktop  # and add the connector to Claude Desktop's config (backup kept)
```

Quit Claude completely (Cmd+Q), reopen it, and open a Code tab session on this folder. A checkout that has a `data/` folder is its own Gatekeeper home, so an existing instance keeps working where it is. Test the plugin itself with `claude --plugin-dir .`.

## Use

| When | Do |
| --- | --- |
| Once | In a Code tab session here: "Run the gatekeeper-setup interview." About forty-five minutes, resumable at any step |
| First run | "Run gatekeeper-run." Watch the first board fill |
| Weekly or daily | Code tab, Scheduled (left sidebar), New task, run on this computer. Folder: this one. Instructions: the prompt in the website's How it works page, under "Running it on a schedule". Schedule: weekly early Monday, or daily before you start work. Run it once while you watch and choose Always allow at each prompt |
| Every morning | Ask in any Claude chat: "Show my Gatekeeper board." Decide each queued item with a one-line reason |

Scheduled runs need the app open and the Mac awake: use Claude's keep-awake setting if your version has one, or stop the Mac sleeping while plugged in. A run missed while asleep catches up once on wake.


## What is enforced in code

- Every figure in a candidate, review, objection or rank note needs a claim: a source (URL, retrieval date, quoted excerpt) or an estimate (confidence, basis). Otherwise the write is rejected and the agent is told which figure.
- Red Team reads ideas with sponsor, origin and source sensor removed.
- Panelists cannot see each other's round-1 reviews; round 2 is anonymized and allowed once.
- Novelty floor, duplicate detection, per-run caps.
- Registrar readiness of 2 needs cited evidence; 3 needs a sourced claim.
- Decisions need a reason. Defaults execute on their date and are recorded as defaults.
- Facts and judgments are append-only in the database (triggers block updates and deletes).
- Rejected writes are logged; `get_pipeline_status` shows which agents are struggling.

## Built vs designed

Built: connector and ledger, all eleven agents, setup interview, daily run, two-round deliberation, decision queue with defaults, stall and drift kill triggers, calibration (exemplar agreement, what-if weights, weekly proposals), chat review.

Not yet built: the pinned board page, the S-curve estimator, competitive-preemption and window-closed kill triggers, resurrection of killed ideas, a hosted ledger for phone access.

## Tests

```
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python tests/smoke_mcp.py
```
