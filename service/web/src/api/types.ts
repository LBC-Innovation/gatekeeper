// The shapes the service returns (service/gatekeeper/views.py). Scores are 0 to 100 here; the ledger keeps 0 to 1.

export type Action = "PROMOTE" | "NEED_EVIDENCE" | "CONSIDER" | "PARK" | "CONTESTED" | "REVIEW_OBJECTION" | "PROTECTED";
export type Verb = "promote" | "need_evidence" | "park" | "kill";
export type Cell = "core" | "adjacent" | "transformational";

export interface QueueView {
  id: number; recommended_action: Action; default_action: string; default_on: string; days_left: number; why: string; snapshot_id: number | null;
}
export interface DecisionView { action: string; reason: string; actor: string; via: string | null; at: string }

export interface IdeaSummary {
  id: string; title: string; thesis: string; cell: Cell | null; four_p: string | null; stage: string; origin: string;
  action: Action | null; score: number | null; band: number | null; rank: number | null; my_rank: number | null; spread: number | null;
  readiness: number | null; readiness_max: number; strategy: number | null; portfolio: number | null;
  severity: number | null; objection_headline: string | null; rounds: number; directive_id: string | null;
  snapshot_id: number | null; snapshot_at: string | null; queue: QueueView | null; decision: DecisionView | null; last_activity_at: string;
}

export interface RunRow { id: number; trigger: string; status: string; started_at: string; finished_at: string | null; note: string | null; counts: Record<string, number> | null }
export interface LiveRun extends RunRow { stages: { stage: string; status: string; detail: string | null; at: string }[]; admitted: number }

export interface InboxItem { kind: "decision" | "objection"; idea: IdeaSummary; queue: QueueView }
export interface Inbox {
  as_of: string | null; items: InboxItem[]; last_run: RunRow | null; live_run: LiveRun | null;
  portfolio: { shares: Record<Cell, number>; target: Record<string, number>; alarms: string[]; in_band: boolean };
  brief: { date: string; body: string; quiet: boolean } | null; queue_size: number; today: string;
}

export interface Board {
  rows: IdeaSummary[]; in_review: number; promoted: IdeaSummary[]; lines: { fund: number; park: number; ready: number }; as_of: string | null;
}

export interface Review {
  role: "analyst" | "steward" | "registrar"; round: 1 | 2; score: number; sub: Record<string, any>; rationale: string; headline: string; headline_authored: boolean;
  confidence: string; revision_reason: string | null; created_at: string;
}
export interface Objection {
  id: number; headline: string; headline_authored: boolean; text: string; severity: number; falsifier: string; status: string; answer: string | null; created_at: string; run_id: number | null;
}
export interface Claim {
  id: number; field: string; statement: string; value: string | null; kind: "source" | "estimate"; url: string | null; retrieved_at: string | null;
  excerpt: string | null; confidence: string | null; basis: string | null; created_by: string;
}
export interface ReadyDim { key: string; label: string; score: number; word: string; gap: string | null; owner_hint: string | null; claim_ids: number[] }
export interface TimelineEvent { id: number; at: string; actor: string; event: string; detail: Record<string, any> | null }

export interface IdeaRecord {
  summary: IdeaSummary; description: string | null; technique: string | null; sponsor: string | null;
  first_check: { smallest_commitment: string; uncertainty_retired: string; what_must_be_true: string } | null;
  problem: { id: string; statement: string; for_whom: string; why_now: string } | null;
  signal: { id: string; sensor: string; title: string; url: string; retrieved_at: string; excerpt: string; status: string } | null;
  siblings: IdeaSummary[]; reviews: Review[];
  readiness: { total: number | null; max: number; dims: ReadyDim[]; enough: boolean | null };
  analyst: { fit: number | null; capability: number | null; directive_id: string | null; gaps: { capability: string; acquisition_path: string }[];
             constraints: { rule: string; applies: boolean; binding: boolean; ceiling: number; capabilities: string[] }[]; dependency: Record<string, any>; round1_fit: number | null } | null;
  steward: { mix_effect: number | null; cannibalization: number | null; overlaps: { id: string; name: string }[] } | null;
  objections: Objection[]; evidence: Claim[]; timeline: TimelineEvent[];
  decisions: { action: string; reason: string; actor: string; created_at: string }[]; arithmetic: string | null;
  rank_notes: { note: string; created_at: string }[]; weights: Record<string, number>; snapshot_id: number | null;
  board_neighbours: { prev: string | null; next: string | null; position: number | null; of: number };
}

export interface Portfolio {
  counts: Record<Cell, number>; shares: Record<Cell, number>; target: Record<string, number>; alarms: string[]; in_band: boolean; floor: number | null;
  items: Record<Cell, { id: string; name: string; kind: string; ambition_cell: Cell }[]>; goals: { id: string; name: string; kind: string; ambition_cell: Cell }[]; candidates: Record<Cell, IdeaSummary[]>; parked_bold: IdeaSummary[];
  overlaps: { item: { id: string; name: string }; ideas: { idea: IdeaSummary; cannibalization: number | null }[] }[];
}

export interface RunsList { runs: RunRow[]; live: LiveRun | null; stages: string[] }
export interface RunDetail {
  run: RunRow; activity: { actor: string; event: string; n: number; start: string; end: string }[];
  stages: { stage: string; status: string; detail: string | null; at: string }[];
  rejections: { tool: string; n: number }[]; rejection_samples: { tool: string; reason: string; created_at: string }[];
  rejections_outside_runs: number; admissions: { idea_id: string; gate_score: number; admitted_at: string }[];
}

export interface SignalRow {
  id: string; run_id: number; sensor: string; title: string; url: string; retrieved_at: string; excerpt: string; status: string; novelty: number | null; curator_note: string | null;
  problem: { id: string; statement: string; for_whom: string; why_now: string } | null; ideas: IdeaSummary[];
}
export interface LogData {
  decisions: { id: number; idea_id: string; title: string; thesis: string | null; action: string; reason: string; actor: string; via: string | null; at: string }[];
  config: { id: number; section: string; reason: string; actor: string; at: string }[];
}
export interface ConfigData {
  weights: Record<string, number>; rules: Record<string, number>; taste: { likes: { text: string; supported_by: string[] }[]; dislikes: { text: string; supported_by: string[] }[] };
  bench: any; directives: { id: string; statement: string; funded?: boolean; retired?: boolean }[]; capabilities: { id: string; name: string; maturity: string }[];
  exclusions: string[]; watchlist: Record<string, string[]>; mix_target: Record<string, number> | null; exploratory_floor: number | null; profile: any; versions: Record<string, number | null>;
}
export interface Proposal { id: number; kind: string; body: any; rationale: string; status: string; created_at?: string }
export interface WhatIf { weights: Record<string, number>; exemplar_agreement: { pairs: number; agreement: number | null }; live_board: { idea_id: string; score: number }[] }
export interface LedgerEvent { id: number; idea_id: string | null; run_id: number | null; at: string; actor: string; event: string; detail: any }

export interface AgentProfile {
  id: string; name: string; epithet: string; stage: "source" | "judge" | "close" | "learn"; schedule: string; can_sit_out: boolean; bio: string;
  avatar: string; model: string | null; file: string | null; can_search_web: boolean; tools: { ledger: string[]; other: string[] };
  markdown?: string | null;
}

export interface RefCard {
  code: string; kind: string; label: string; title: string; lede: string | null; href: string | null;
  facts: [string, string][]; related: { code: string; title: string }[];
}
