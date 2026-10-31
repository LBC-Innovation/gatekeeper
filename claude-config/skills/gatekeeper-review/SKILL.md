---
name: gatekeeper-review
description: Review and act on the Gatekeeper board in chat - show the board or queue, open an idea record, decide, rank, answer objections, request evidence, check pipeline status, change configuration or weights, and accept or reject calibration proposals. Use whenever the person asks about their ideas, board, queue, brief, pipeline, or Gatekeeper settings.
---

# Reviewing Gatekeeper in chat

The person is the decision-maker. You show what the ledger says, help them think, and record what they decide. You never decide for them.

## Show the board

`get_board` (pass filters when asked: `cell`, `four_p`, `action`, `min_score`). Render:

1. One header line: signals this week, kept, waiting on you, exploratory live vs floor.
2. Alarms, or the words "Portfolio in band."
3. A table: rank, idea id, thesis (short), cell, fit, capability, readiness, score with band (0.74 ± 0.06), action, your rank if set.
4. The decision queue: each item with recommended action and "default <action> on <date>".

Use only numbers the tools return. Round to two decimals.

## Open an idea

`get_idea_record`. Present four blocks, in this order:

1. **Deliberation**: the arithmetic line, each panelist's score and rationale, round-2 revisions with their reasons, the Arbiter's note.
2. **Objection**: Red Team's case verbatim, its severity, its status, and the falsifier.
3. **Evidence**: every claim with its source link and date, estimates marked as estimates with confidence.
4. **What happens next**: the first check (smallest commitment, uncertainty retired, what must be true), the readiness worklist, and capability gaps.

## Act

| The person says | You call |
| --- | --- |
| "Promote / kill / park 0147" | `decide`. If they gave no reason, ask for one line; it is how the system learns. Never invent the reason |
| "Need evidence on 0147: <what to find out>" | `decide` with `need_evidence`, their words as the reason |
| "Keep it" (on a kill recommendation) | `decide` with `keep` and their reason |
| "I'd rank these A, B, C" | `set_my_rank`, then report where they disagree with the board |
| "That objection is answered because..." | `answer_objection` with status `answered`, or `accepted` if they accept the risk |
| "Find out whether..." | `request_evidence` with role `registrar` (is the case built?) or `analyst` (fit, capability, competition); it runs at the start of the next pipeline run |
| "Add my idea: ..." | `submit_my_idea`; it goes on the board protected and unscored |
| "What's pending?" / "Did last night run?" | `get_pipeline_status`: runs, pending jobs, rejected writes, ideas by stage |

## Change configuration

1. `get_config` for the section. Show the current value.
2. Draft the change and show it as before and after.
3. For weights, run `what_if_weights` first and show how the board and exemplars would re-rank.
4. Save with `set_config` only after the person confirms, with their reason. Changing strategy or capabilities queues re-scores for the next run; say so.

## Calibration proposals

`list_proposals`. Show each with its evidence. `decide_proposal` with the person's answer and reason.

## Rules

- Never call pipeline write tools (`submit_signal`, `curate_signal`, `submit_candidate`, `submit_*_review`, `raise_objection`) from a review conversation.
- Never record a decision the person did not make.
- Keep the person's words as the reason; do not polish them.
