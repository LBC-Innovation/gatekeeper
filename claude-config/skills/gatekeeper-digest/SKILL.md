---
name: gatekeeper-digest
description: Write the weekly Gatekeeper digest, an email the person can reply to in order to decide, and record their replies as decisions. Use when the person says "write this week's digest", "weekly digest", "draft the digest email", or "record this reply" during the digest test (docs/web-app-review/04-digest-test-plan.md).
---

# Weekly digest

The digest replaces the run brief for the person. It is one email, read on a phone in under three minutes, that ends in a reply. It leads with the one decision that matters most and says what the cheapest next step is. Everything in it comes from the ledger. Nothing in it is invented.

This skill only reads the ledger when writing. It writes to the ledger only when recording a reply the person actually sent.

## Write the digest

### 1. Gather
- `get_queue`: the decisions waiting.
- `get_board`: the header, alarms and portfolio balance.
- `get_idea_record` for each queued idea: the thesis, the first check, the objection with its falsifier, the Arbiter's note, and each panelist's latest score.
- `get_decisions`: what closed by default since the last digest, and whether the person has decided anything yet.
- If the board's alarms say the exploratory floor is breached, look up the best transformational idea in `get_decisions` or `get_board` (it may be parked), and its record.

### 2. Choose the lead
The lead is the queued item whose decision changes the most. Prefer, in order: an item with a serious objection (0.70 or more), then the item where the panel split widest and the first check is cheapest, then the highest score. If two or more queued ideas answer the same problem, present them as one decision with options and say which one the panel prefers (the highest score). Never hide an option: list the others by short title.

### 3. Write

Save to `digests/YYYY-MM-DD.md` (today's date) with exactly this structure:

```markdown
Subject: <lead in plain words, under 60 characters> · <n> decisions by <weekday d Mon>

Good morning. <n> decisions this week. The first one matters most.

**1. <short title>** · <panel state>
<one or two sentences: what it is, why it fits, in the company's words>
**The case against:** <the objection in two sentences, plainly>
**Cheapest check:** <the first check, as an action someone could start Monday>
**What would change the panel's mind:** <the falsifier in one sentence>
Reply: **Fund the check**, **Find out first** (say what), **Park**, or **Kill**, with a line on why.

**2. <short title>** · <panel state> · Strength <0-100>
<two sentences> Cheapest check: <one line>.

**3. ...**

**Portfolio:** <one line in plain words. Name the gap, not the percentages, unless the gap is the point>

<If anything closed by default since the last digest: one honest line naming it, and "Reply 'bring back <title>' to reopen it.">

If you don't reply by <weekday d Mon>, <each unanswered item is parked at the next run / what the default actually is>.

*So far: <n> decided by you · <n> closed by default · <n> objections unanswered.*
*Ask "why" about any item and you'll get the panel's reasoning.*

---
Operator notes (delete before sending): idea ids, scores and weights used, so a reply can be recorded.
```

### Voice and vocabulary
- Write for an executive, not an analyst. One idea per sentence. No system vocabulary in the body:

| Internal | In the digest |
| --- | --- |
| IDEA-2026-0023 | a short title (5 to 8 words) you write from the thesis |
| SD-03, CAP-07, PF-0006 | the name: "getting red light live", "the red light prototype" |
| score 0.4466 | Strength 45 (out of 100, rounded) |
| band, spread, dispersion | "the panel is split", "one serious objection" |
| CONTESTED | "Panel is split" |
| REVIEW_OBJECTION | "Serious objection, needs your answer" |
| NEED_EVIDENCE | "Find out first" |
| PROMOTE | "Fund the check" |
| PARK | "Park" |
| falsifier | "what would change the panel's mind" |
| Analyst / Steward / Registrar | the strategy, portfolio and readiness reviewers |

- Every fact comes from a record. If a number is not in the tool output, leave it out.
- Say the default honestly. Today's engine parks unanswered items at the first run on or after their date. Do not promise to ask again or hold an item.
- A quiet week: three lines. "Nothing needs you this week." One line on the closest idea. The footer.
- No emoji. No em dashes. No adjectives doing the work of evidence.

### 4. Show it
Show the digest in chat. Tell the person the file path and that the operator notes at the bottom are for recording replies, not for sending.

## Record a reply

The person (or the operator, pasting the person's email) gives a reply. Record only what the reply says. Never infer a decision from silence, tone or a question.

| The reply says | Call |
| --- | --- |
| Fund the check on N | `decide(idea, "promote", <their words>)` |
| Find out first on N: <what> | `decide(idea, "need_evidence", <their words>)` then `request_evidence(idea, <what>, role)` |
| Park N / Kill N | `decide(idea, "park" or "kill", <their words>)` |
| Bring back <title> | `decide(idea, "need_evidence", <their words>)` |
| The objection on N is wrong because... | `answer_objection(objection_id, <their words>, "answered")` |
| I accept that risk on N | `answer_objection(objection_id, <their words>, "accepted")` |
| A question ("why does...?") | Answer it from `get_idea_record`. Record nothing |

- The reason is their words, unpolished. If they gave no reason, ask for one line before recording. `decide` rejects reasons under three words.
- If the reply is ambiguous ("looks good"), ask which action they mean. Do not pick one.
- After recording, add a row to the log in `docs/web-app-review/04-digest-test-plan.md`: week, participant, replied, decided by person, reason given, why-questions.
