import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { AgentProfile, Board, ConfigData, Inbox, IdeaRecord, LedgerEvent, LogData, Portfolio, Proposal, RunDetail, RunsList, SignalRow, RefCard } from "./types";

export const useInbox = () => useQuery({ queryKey: ["inbox"], queryFn: () => api.get<Inbox>("/api/inbox") });
export const useBoard = () => useQuery({ queryKey: ["board"], queryFn: () => api.get<Board>("/api/board") });
export const useIdea = (id: string | undefined) => useQuery({ queryKey: ["idea", id], queryFn: () => api.get<IdeaRecord>(`/api/ideas/${id}`), enabled: !!id });
export const usePortfolio = () => useQuery({ queryKey: ["portfolio"], queryFn: () => api.get<Portfolio>("/api/portfolio") });
export const useRuns = () => useQuery({ queryKey: ["runs"], queryFn: () => api.get<RunsList>("/api/runs") });
export const useRun = (id: number | undefined) => useQuery({ queryKey: ["run", id], queryFn: () => api.get<RunDetail>(`/api/runs/${id}`), enabled: id != null });
export const useSignals = () => useQuery({ queryKey: ["signals"], queryFn: () => api.get<{ signals: SignalRow[] }>("/api/signals") });
export const useLog = () => useQuery({ queryKey: ["log"], queryFn: () => api.get<LogData>("/api/log") });
export const useConfig = () => useQuery({ queryKey: ["config"], queryFn: () => api.get<ConfigData>("/api/config") });
export const useProposals = () => useQuery({ queryKey: ["proposals"], queryFn: () => api.get<{ open: Proposal[]; accepted: Proposal[]; rejected: Proposal[] }>("/api/proposals") });

/**
 * Keeps every screen current while a run is in progress. The service streams ledger events (resumable by id);
 * we invalidate the queries an event can change, debounced so a burst of writes causes one refetch.
 */
export function useLedgerStream(onEvent?: (e: LedgerEvent) => void) {
  const qc = useQueryClient();
  useEffect(() => {
    let timer: number | undefined;
    const es = new EventSource("/api/stream");
    const refresh = (e: LedgerEvent) => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        for (const k of ["inbox", "board", "portfolio", "runs", "signals", "log"]) qc.invalidateQueries({ queryKey: [k] });
        if (e.idea_id) qc.invalidateQueries({ queryKey: ["idea", e.idea_id] });
        if (e.run_id) qc.invalidateQueries({ queryKey: ["run", e.run_id] });
      }, 400);
    };
    es.addEventListener("ledger", (m) => {
      const ev = JSON.parse((m as MessageEvent).data) as LedgerEvent;
      refresh(ev);
      onEvent?.(ev);
    });
    return () => { window.clearTimeout(timer); es.close(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qc]);
}

export const useAgents = () => useQuery({ queryKey: ["agents"], queryFn: () => api.get<{ agents: AgentProfile[] }>("/api/agents"), staleTime: 60_000 });
export const useAgent = (id: string | null) => useQuery({ queryKey: ["agent", id], queryFn: () => api.get<AgentProfile>(`/api/agents/${id}`), enabled: !!id, staleTime: 60_000 });

export const useRefCard = (code: string | null) => useQuery({ queryKey: ["ref", code], queryFn: () => api.get<RefCard>(`/api/refs/${code}`), enabled: !!code, staleTime: 60_000, retry: false });
