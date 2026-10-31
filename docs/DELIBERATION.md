# How the panel deliberates

Agents supply judgments. Code turns judgments into a ranking. Every number on the board can be reproduced by hand from the ledger, and every step below is enforced by the connector (`server/gatekeeper/deliberation.py` and `core.py`), not by prompts.

## The panel

| Member | Question it answers | Score | Default weight |
| --- | --- | --- | --- |
| Analyst | Does it serve a directive, and can we build it? | mean of strategic fit and capability match | 0.35 |
| Steward | Does it balance the portfolio or worsen it, and does it eat an existing line? | portfolio score | 0.30 |
| Registrar | Is the idea ready for its next gate, funding the first check? | six readiness dimensions for that gate, 0 to 3 each, total / 18 | none: gates PROMOTE, not in the score |
| Red Team | What is the strongest argument against it? | objection severity, 0 to 1 | 0.15 (band, not score) |

Scouts, Curator, Framer and Inventor carry no weight. They find and shape; they do not judge.

## Five stages

1. **Gate.** The Analyst reviews every candidate first. Below 0.30 the idea is parked automatically, with the reason recorded. Only the top five by Analyst score per run go to the full panel; the rest wait for the next run.
2. **Round 1, independent and blind.** Registrar, Steward and Red Team review at the same time. No panelist sees another's work. Red Team reads the idea with sponsor, origin and source sensor removed.
3. **Trigger.** A second round runs only if the voting panel is split (Analyst and Steward round-1 scores spread by 0.25 or more) or Red Team raised a serious objection (severity 0.50 or more). Otherwise the panel's first answer stands.
4. **Round 2, structured exchange.** Each panelist receives the objection and the other panelists' rationales, anonymized, plus the spread. Each may revise once per review cycle and must give a reason either way. A later re-score (after a strategy change) starts a new cycle. This is a Delphi round: people move only when an argument moves them, and the ledger records why.
5. **Resolve, in code.**

```
score = (wA x Analyst + wS x Steward) / (wA + wS)
band  = w_redteam x (highest open objection severity)
```

The latest review per role counts. Red Team's latest objection on an idea replaces its earlier open one, which stays in the ledger marked superseded. A benched role is left out and the remaining weights are renormalized; it is never counted as zero.

## Why the Registrar does not vote

Until 27 October 2026 the Registrar's readiness was a fifth of the score. It measured a different thing (is the case built) on a scale that sits near 0.2 for any idea framed that morning, because a new idea has no resource plan or sponsor yet. Averaged in, it capped every score below the promote line. Counted in the spread, it made seven of ten ideas look contested when the panel actually agreed. Now the Registrar scores readiness for the gate the idea is at, funding its first check (stage-gate requirements grow by gate; invest late, fail early), and that readiness decides fund the check versus find out first.

## Why the objection does not average in

Averaging a criticism into a score launders it into a rounding error. Instead, Red Team's dial sets how wide the confidence band is. An open objection of severity 0.70 or more puts the idea in your queue whatever its score: a 0.90 idea with an unanswered objection still lands in front of you.

## From score to action

| Condition (checked in this order) | Action |
| --- | --- |
| Open objection, severity 0.70 or more | REVIEW_OBJECTION |
| Spread still 0.25 or more after round 2 | CONTESTED |
| Score 0.65 or more, readiness 0.34 or more | PROMOTE |
| Score 0.65 or more, readiness below 0.34 | NEED_EVIDENCE |
| Score below 0.45 | PARK |
| Between, readiness below 0.34 | NEED_EVIDENCE |
| Otherwise | CONSIDER |
| Your own idea (protected channel) | PROTECTED, unscored, never defaulted |

All thresholds live in the `rules` config and can be changed with a reason.

## Your queue

At most three open decisions at a time (the `queue_size` rule). Objections first, then contested, then by score. Your own protected ideas stay on the board and never enter the queue, so no default can park them. One slot is reserved for the best transformational idea, ranked on the panel's score only, so your past preferences cannot crowd out exploration.

Each queued item has a default action and a date (seven days by default). If you do not decide, the default executes at the next run and is recorded as a default, not as your decision. Defaults are conservative: park, or need evidence.

## Kill recommendations

For promoted ideas, two triggers need no outside data:

- **Stall.** Days idle divided by the typical gap between events for promoted ideas (14 days until there is history). At 3x or more, a kill is recommended.
- **Strategic drift.** The directive the Analyst matched has been retired.

A kill recommendation defaults to kill. Keeping the idea requires a reason, and that reason is data.

## Learning what you value

- Every decision needs a one-line reason.
- You can drag your own ordering. Pairs you order differently from the board are the strongest calibration signal.
- Weekly, the Calibrator proposes weight, taste or rule changes, each citing the decisions behind it. You accept or reject. Nothing changes without you.
- `what_if_weights` previews any change against the exemplars and the live board before you commit.

## Concepts this implements

| Concept | Where |
| --- | --- |
| Stage-gate checkpoint requirements | Registrar's six readiness dimensions, judged for the gate the idea is at (its first check) |
| Invest late, fail early; real options | Every candidate's first check; kill defaults; time-to-kill |
| Psychological safety, Edmondson | Red Team absorbs the social cost of the objection; blind to sponsor |
| Fitzgerald, two opposing ideas | Objection kept beside the score as a band, never averaged away |
| Ambition matrix, portfolio balance | Steward's mix effect, alarms, reserved exploratory slot |
| Drucker's seven sources | One scout per opportunity area |
| Activity vs impact metrics | Run counts vs decisions, kills and calibration agreement |
