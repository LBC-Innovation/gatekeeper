/**
 * A decision is written to an append-only ledger, so "undo" has to happen before the write.
 * The write waits five seconds. If the tab is closed or hidden first, it is sent at once (keepalive), never dropped.
 * An Idempotency-Key makes a flush that races the timer safe: the service records one decision.
 */
import { useSyncExternalStore } from "react";

interface Pending { send: (keepalive: boolean) => Promise<void>; timer: number; ideaId: string; verb: string }
const pending = new Map<string, Pending>();
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((f) => f());

export function commitAfter(key: string, ms: number, ideaId: string, verb: string, send: (keepalive: boolean) => Promise<void>): () => void {
  const timer = window.setTimeout(() => { pending.delete(key); notify(); void send(false); }, ms);
  pending.set(key, { send, timer, ideaId, verb });
  notify();
  return () => { window.clearTimeout(timer); pending.delete(key); notify(); };
}

/** The verb waiting to be written for an idea, if any. Lets the screen show the decision at once. */
export const usePendingVerb = (ideaId: string) =>
  useSyncExternalStore((fn) => { listeners.add(fn); return () => listeners.delete(fn); }, () => [...pending.values()].find((p) => p.ideaId === ideaId)?.verb);

if (typeof window !== "undefined") {
  window.addEventListener("pagehide", () => {
    for (const [key, p] of pending) { window.clearTimeout(p.timer); pending.delete(key); void p.send(true); }
  });
}
