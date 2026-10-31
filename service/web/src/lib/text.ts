import type { Action, Cell, Verb } from "../api/types";

/** The plain-English word for what the panel recommends. Engine labels never reach the screen. */
export const STATUS: Record<Action, string> = {
  PROMOTE: "Panel says fund", NEED_EVIDENCE: "Find out first", CONSIDER: "Your call", PARK: "Below the park line",
  CONTESTED: "Split panel", REVIEW_OBJECTION: "Serious objection", PROTECTED: "Your idea",
};
export const CELLS: Record<Cell, string> = { core: "Core", adjacent: "Adjacent", transformational: "Transformational" };

export const VERBS: { id: Verb; key: string; label: string; hint: string }[] = [
  { id: "promote", key: "1", label: "Fund the check", hint: "Fund the smallest commitment, with an owner" },
  { id: "need_evidence", key: "2", label: "Find out first", hint: "Ask the panel to settle one uncertainty" },
  { id: "park", key: "3", label: "Park", hint: "Set it aside. It returns if the falsifier is met" },
  { id: "kill", key: "4", label: "Kill", hint: "Close it. Your reason teaches the panel" },
];
export const OUTCOME: Record<string, string> = { promote: "Funded", need_evidence: "Find out first", park: "Parked", kill: "Killed", keep: "Kept" };
export const recommendedVerb = (a: Action | null): Verb | null =>
  ({ PROMOTE: "promote", CONSIDER: "promote", NEED_EVIDENCE: "need_evidence", CONTESTED: "need_evidence", REVIEW_OBJECTION: "need_evidence", PARK: "park" } as Record<string, Verb>)[a ?? ""] ?? null;

/** Reasons offered as one-tap chips. They come from the taste lines, so a decision reads in the person's own terms. */
export const CHIPS: Record<Verb, string[]> = {
  promote: ["Fastest path to live", "Reuses what we already run", "Cheap to learn", "A new RFP opening", "Competitors are starting to offer it", "Agencies are asking for it"],
  need_evidence: ["The falsifier is cheap to check", "Law status is unclear", "Need one buyer to say yes", "Numbers are not sourced", "Panel is split on a fact", "Check reads the wrong document"],
  park: ["Timing is wrong", "We cannot staff it (the ALPR lesson)", "Another unfinished MVP", "Depends on an asset we do not own", "Incumbents hold the market", "The law is not there yet"],
  kill: ["Off strategy", "We cannot staff it (the ALPR lesson)", "Depends on an asset we do not own", "Incumbents hold the market", "Already covered by work in flight", "The objection is fatal"],
};

/** Any engine label or field name an agent wrote into prose reads as words. */
export function humanize(t: string | null | undefined): string {
  return (t ?? "")
    .replace(/\b(REVIEW_OBJECTION|NEED_EVIDENCE|CONTESTED|CONSIDER|PROMOTE|PARK|PROTECTED)\b/g, (m) => STATUS[m as Action].toLowerCase())
    .replace(/\bneed_evidence\b/g, "find out first")
    .replace(/\b([a-z]+(?:_[a-z]+)+)\b/g, (m) => m.replace(/_/g, " "));
}

const CLAIM_REF = /\b[Cc]laims?\s*(?:ids?\s*)?#?\d+(?:\s*(?:,|\/|&|and|or|to|-|–)\s*#?\d+)*/g;

/** Split prose into text and claim references, so a reference can link to the evidence it points at. */
export function splitClaimRefs(text: string): { text: string; ids?: number[] }[] {
  const out: { text: string; ids?: number[] }[] = [];
  let last = 0;
  for (const m of text.matchAll(CLAIM_REF)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ text: text.slice(last, at) });
    out.push({ text: m[0], ids: (m[0].match(/\d+/g) ?? []).map(Number) });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}

export function fmtDay(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { weekday: "short", day: "numeric", month: "short" });
}
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short" });
}
export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
}
export const domain = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; } };
export const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

const DEFAULT_STATE: Record<string, string> = { park: "Parked", need_evidence: "Find out first", kill: "Killed" };

/** The status an idea is updated to if the person does nothing, as it appears in the lists: "updated to Parked on Wed, Nov 4". */
export const defaultUpdate = (q: { default_action: string; default_on: string }) =>
  `updated to ${DEFAULT_STATE[q.default_action] ?? "a new status"} on ${fmtDay(q.default_on)}`;

/** What happens if the person does nothing, as one sentence. */
export function defaultSentence(q: { default_action: string; default_on: string } | null): string {
  if (!q) return "No automatic update. It waits for you.";
  return `Updates to ${DEFAULT_STATE[q.default_action] ?? "a new status"} on ${fmtDay(q.default_on)} unless you decide.`;
}

export const strengthWord = (s: number | null, fund: number, park: number) =>
  s == null ? "not scored" : s >= fund ? "above the fund line" : s >= park ? "between the park line and the fund line" : "below the park line";

const ID_CODE = /\b(?:SD-\d{2}|CAP-\d{2}|PF-\d{4}|(?:IDEA|SIG|PRB)-\d{4}-\d{4})\b/g;

/** Split prose into text and ID codes, so each code can open its card. */
export function splitIdCodes(text: string): { text: string; code?: string }[] {
  const out: { text: string; code?: string }[] = [];
  let last = 0;
  for (const m of text.matchAll(ID_CODE)) {
    const at = m.index ?? 0;
    if (at > last) out.push({ text: text.slice(last, at) });
    out.push({ text: m[0], code: m[0] });
    last = at + m[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last) });
  return out;
}
