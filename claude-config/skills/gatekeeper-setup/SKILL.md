---
name: gatekeeper-setup
description: Run the Gatekeeper setup interview, or resume it. Use when the person says "set up Gatekeeper", "run the interview", "start setup", or when get_setup_status shows setup incomplete. Reads the public record first, then asks only what it cannot read, in seven steps.
---

# Gatekeeper setup interview

The interview runs once, takes about forty-five minutes, and can stop and resume at any step. It does not open with a questionnaire. It reads everything public first, so every question asked is one only the person can answer. Correcting a draft is faster and more accurate than authoring from a blank page, and executives describing their own company leave out what they consider obvious.

Everything the interview learns is saved through the `gatekeeper` connector with `set_config`, `add_portfolio_item` and `add_exemplar`. Never write config files by hand.

## Ground rules

- Start every session with `get_setup_status` and resume at `next_step`. Tell the person: "Step N of 7: <name>."
- Ask one or two questions at a time. Use AskUserQuestion for choices; use plain questions for anything open.
- Show drafts as short bullet lists the person can correct, never as essays.
- Every fact drafted from the web carries the URL it came from. If you did not read it, do not draft it.
- No invented figures anywhere. If the person gives a number, use theirs.
- Save after each step, with a reason like "setup step 3: directives confirmed by the person". A saved step survives an interrupted session.

## Step 1. Read the public record

Ask for one or more URLs: corporate site, products, newsroom, careers, investor or public documentation.

Open each with WebFetch, and follow up to five obviously useful links (product pages, press releases, open roles). If the person has a skill that describes their company's domain, load it as an additional source and say so.

Draft, with a source on each line:

| What the public record tells you | Draft |
| --- | --- |
| What they make and who buys it | |
| How they position and price | |
| What they announced this year | |
| What they are hiring for, and where | |
| Which partners and platforms they name | |

Save: `set_config("profile", {"company", "urls", "summary", "sources": [...], "confirmed": false}, reason)`.

## Step 2. Confirm and correct

Show the draft. Ask: "What is wrong, missing, or out of date?" Apply corrections. Save the profile again with `"confirmed": true`.

## Step 3. Tell it what it cannot read

Ask these, a couple at a time:

1. **Directives.** Propose three to six candidate directives inferred from the public record. Ask which are real, which are genuinely funded, what is missing, and the horizon for each. Assign ids SD-01, SD-02, and so on.
2. **Innovation surface.** "Are we hunting new offerings, better internal processes, business models, or all three?" (multi-select). A company that wants process innovation and never says so gets a board full of products.
3. **Off limits.** "What is off limits, and why?" Each becomes an exclusion line.
4. **Mix.** Offer the default target (core 0.60, adjacent 0.30, transformational 0.10, tolerance 0.05), exploratory floor 2, novelty floor 0.35. Ask whether to keep or change.
5. **Watch list.** Propose two to five public search terms for each external Drucker area that applies (`industry_market_change`, `demographics`, `perception_shifts`, `new_knowledge`). Explain that scouts may search only with these terms, so they must be safe to type into a public search engine: no confidential project names, customer names, or directive wording. For the internal areas (`unexpected_occurrences`, `incongruities`, `process_needs`), the "terms" are the names of the exports the person will drop in `inbox/` (for example `tickets.csv`, `ado-workitems.csv`); leave an internal area out until there is an export for it.

Save: `set_config("strategy", {...}, reason)`. The connector validates the shape and tells you exactly what to fix.

## Step 4. Connect what is not public

The first two are not optional; without them the Steward cannot judge balance and the pipeline will recommend things already in flight.

1. **Current lines.** "List the product and service lines you sell today." Any format: a pasted list, or an export dropped into the inbox folder that you read (`get_setup_status` returns its path as `inbox`; tell the person where it is). For each, ask or propose its cell (core, adjacent, transformational) and confirm. `add_portfolio_item(kind="line", ..., source="told by the person in setup")`.
2. **In flight.** "What is already funded and in progress?" Same treatment with `kind="in_flight"`.
3. **Capabilities.** Draft from the profile; ask maturity (research, prototype, production) for each. Then: "What could you get within a year if you had to, and how: hire, partner, buy or build?" Save `set_config("capabilities", ...)`.
4. **Two questions for later.** "Which idea did you kill and still regret?" and "Where does the portfolio actually hurt?" Keep the regret for step 7. Add the pain points to the profile as `pain_points` and save the full profile again (it keeps its confirmation).

## Step 5. Assemble the team

Explain the bench in one short table: Scout, Curator, Framer, Inventor, Analyst, Registrar, Steward, Red Team, Arbiter, Herald, Calibrator. Analyst and Registrar always play. Ask whether any of Steward, Red Team, Framer, Inventor or Calibrator should sit out, and why. Examples: a start-up with no portfolio benches Steward; a culture that already argues well may bench Red Team. Sitting out is a legitimate answer recorded with its reason.

Save: `set_config("bench", {"benched": [{"role": ..., "reason": ...}]}, reason)`. Save an empty list if everyone plays.

## Step 6. Set the weights

Four dials, anchored to decisions already made, not typed in the abstract.

1. Show the defaults: Analyst 0.35, Steward 0.30, Registrar 0.20, Red Team band 0.15.
2. Ask about two or three real past decisions: "When you funded X, was it mainly because it fit strategy, because it balanced the book, or because the case was already built?" Fit points to Analyst, balance to Steward, a built case to Registrar.
3. Ask: "When a serious objection is still unanswered, how much should that widen the uncertainty: a little (0.10), the default (0.15), or a lot (0.25)?"
4. Propose weights from the answers, explain them in one line each, and save with `set_config("weights", ..., reason)`.

## Step 7. Calibrate

1. Collect exemplars: at least three, including at least one the person is glad they funded and at least one that should rank low. Twelve to twenty is better if the person has the patience. Outcomes:
   - `funded`: funded and glad they did
   - `regret_funded`: funded, but in hindsight should have said no (common in a company that never kills ideas)
   - `killed`: declined or stopped, rightly
   - `regret_killed`: declined, and wish they had funded it

   For each: a one-sentence thesis, the outcome, the cell, four_p, and the real reason. `add_exemplar`.
2. `start_run("calibration")`. Then call `list_panel_work` and, for every exemplar in `exemplars_unreviewed`, spawn the panel in parallel in a single message: `gatekeeper-analyst`, `gatekeeper-registrar`, `gatekeeper-steward`, and `gatekeeper-redteam` (unless benched). Exemplars skip the analyst gate, so all four can run at once. Prompt each with: "Calibration run <id>. Review exemplar <IDEA-id>, round 1. Follow your instructions."
3. If `list_panel_work` lists any exemplar under `round2`, run round 2 for the listed roles.
4. `calibration_report`. Show the person the ranking next to the real outcomes, and the agreement rate.
5. If the ranking contradicts their judgement, the weights are wrong, not their judgement. Try alternatives with `what_if_weights`, show the effect, and save the set they accept.
6. When they agree with the ranking, `mark_calibrated` with a one-line note of what they accepted, then `finish_run`.

## When setup is complete

Tell the person, in three lines:

- Setup is complete and saved.
- Next: run `gatekeeper-run` once by hand to see the first board.
- Then schedule it daily (Code tab, Routines, New routine, Local, in any folder, instructions: "Run the gatekeeper-run skill.").
