import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api/client";
import type { IdeaSummary, Objection, Verb } from "../api/types";
import { commitAfter } from "../lib/pending";
import { CHIPS, VERBS, defaultSentence, recommendedVerb } from "../lib/text";
import { Button, Dialog } from "../ui/primitives";
import { useToast } from "../ui/toast";

const words = (s: string) => s.trim().split(/\s+/).filter(Boolean).length;

function useRefresh() {
  const qc = useQueryClient();
  return () => { for (const k of ["inbox", "board", "idea", "log", "portfolio"]) qc.invalidateQueries({ queryKey: [k] }); };
}

// ---- Decide ------------------------------------------------------------------------------------------------
export function DecisionSheet({ idea, initial, onClose }: { idea: IdeaSummary; initial?: Verb | null; onClose: () => void }) {
  const toast = useToast();
  const refresh = useRefresh();
  const rec = recommendedVerb(idea.action);
  const [verb, setVerb] = useState<Verb>(initial ?? rec ?? "need_evidence");
  const [chips, setChips] = useState<Set<string>>(new Set());
  const [text, setText] = useState("");
  const reason = [...chips, text.trim()].filter(Boolean).join("; ");
  const ok = words(reason) >= 3 && reason.length >= 10;
  const v = VERBS.find((x) => x.id === verb)!;

  const submit = () => {
    if (!ok) return;
    onClose();
    const key = crypto.randomUUID();
    const send = async (keepalive: boolean) => {
      try {
        await api.post(`/api/ideas/${idea.id}/decisions`, { action: verb, reason, seen_snapshot_id: idea.snapshot_id }, { "Idempotency-Key": key }, keepalive);
        toast.show("Recorded as your decision.");
      } catch (e) {
        const msg = e instanceof ApiError ? e.detail : "The decision could not be recorded.";
        toast.show(msg, { tone: "error", ms: 8000 });
      } finally { refresh(); }
    };
    const cancel = commitAfter(key, 5000, idea.id, verb, send);
    toast.show(<><b>{v.label}</b> · {idea.title}</>, { undo: () => { cancel(); toast.show("Undone. Nothing was recorded."); }, ms: 5000 });
    refresh();
  };

  return (
    <Dialog onClose={onClose} label={`Decide: ${idea.title}`}>
      <form className="space-y-5 p-6" onSubmit={(e) => { e.preventDefault(); submit(); }}
        onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); submit(); } }}>
        <div><p className="text-meta text-ink-2">Decide</p><h2 className="text-title">{idea.title}</h2></div>
        <div role="radiogroup" aria-label="Decision" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {VERBS.map((x) => (
            <button key={x.id} type="button" role="radio" aria-checked={x.id === verb} onClick={() => { setVerb(x.id); setChips(new Set()); }}
              className={`rounded border p-3 text-left ${x.id === verb ? "border-accent bg-sunken" : "border-rule-strong hover:bg-sunken"}`}>
              <div className="flex items-center justify-between font-semibold">{x.label}<span className="kbd">{x.key}</span></div>
              <div className="mt-0.5 text-meta text-ink-2">{x.hint}</div>
            </button>
          ))}
        </div>
        {rec && rec !== verb && <p className="text-meta text-ink-2">The panel suggested {VERBS.find((x) => x.id === rec)!.label.toLowerCase()}. Going against it is fine, and your reason is the most useful calibration there is.</p>}
        <fieldset>
          <legend className="mb-2 font-semibold">Why? <span className="font-normal text-ink-2">Pick one or more, or say it in your words.</span></legend>
          <div className="flex flex-wrap gap-2">
            {CHIPS[verb].map((c) => (
              <button key={c} type="button" aria-pressed={chips.has(c)} onClick={() => setChips((s) => { const n = new Set(s); n.has(c) ? n.delete(c) : n.add(c); return n; })}
                className={`min-h-9 rounded-full border px-3 text-meta ${chips.has(c) ? "border-accent bg-sunken text-accent" : "border-rule-strong hover:bg-sunken"}`}>{chips.has(c) ? "✓ " : ""}{c}</button>
            ))}
          </div>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2} placeholder="Or say it in one line, in your words"
            className="mt-3 w-full rounded border border-rule-strong bg-canvas px-3 py-2 outline-none placeholder:text-ink-2 focus:border-accent" />
        </fieldset>
        {verb === "park" && <p className="text-meta text-ink-2">Parked ideas return if the objection's falsifier is met.</p>}
        <div className="-mx-6 flex items-center gap-3 border-t border-rule px-6 pt-4">
          <span className={`flex-1 text-meta ${ok ? "text-ink-2" : "text-alert"}`}>{ok ? "Recorded as your decision, with your words. You have 5 seconds to undo." : "A reason is required. It is how Gatekeeper learns what you value."}</span>
          <Button kind="ghost" onClick={onClose}>Cancel <span className="kbd">Esc</span></Button>
          <Button type="submit" kind="primary" disabled={!ok}>{v.label}</Button>
        </div>
      </form>
    </Dialog>
  );
}

// ---- Answer an objection ----------------------------------------------------------------------------------------
export function AnswerSheet({ idea, objection, onClose }: { idea: IdeaSummary; objection: Objection; onClose: () => void }) {
  const toast = useToast();
  const refresh = useRefresh();
  const [mode, setMode] = useState<"answered" | "accepted">("answered");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const ok = words(text) >= 3;
  const go = async () => {
    setBusy(true);
    try {
      await api.post(`/api/objections/${objection.id}/answers`, { answer: text.trim(), status: mode });
      toast.show(mode === "accepted" ? "You accepted the risk." : "Your answer is recorded."); refresh(); onClose();
    } catch (e) { toast.show(e instanceof ApiError ? e.detail : "That could not be saved.", { tone: "error", ms: 8000 }); setBusy(false); }
  };
  return (
    <Dialog onClose={onClose} label={`Answer the objection on ${idea.title}`}>
      <form className="space-y-5 p-6" onSubmit={(e) => { e.preventDefault(); if (ok) void go(); }}>
        <div><p className="text-meta text-ink-2">Answer the objection</p><h2 className="text-title">{idea.title}</h2></div>
        <p className="serif text-lead">{objection.headline}</p>
        <div><p className="text-meta font-semibold text-ink-2">What would answer it</p><p className="text-ink-2">{objection.falsifier}</p></div>
        <div role="radiogroup" className="grid grid-cols-2 gap-2">
          {([["answered", "Rebut it", "You have evidence or an argument that answers it."], ["accepted", "Accept the risk", "It is real and you will go on anyway."]] as const).map(([k, l, h]) => (
            <button key={k} type="button" role="radio" aria-checked={mode === k} onClick={() => setMode(k)} className={`rounded border p-3 text-left ${mode === k ? "border-accent bg-sunken" : "border-rule-strong hover:bg-sunken"}`}>
              <div className="font-semibold">{l}</div><div className="text-meta text-ink-2">{h}</div>
            </button>
          ))}
        </div>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} placeholder="Your answer, in your words"
          className="w-full rounded border border-rule-strong bg-canvas px-3 py-2 outline-none placeholder:text-ink-2 focus:border-accent" />
        <div className="-mx-6 flex justify-end gap-3 border-t border-rule px-6 pt-4">
          <Button kind="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" kind="primary" disabled={!ok || busy}>Save answer</Button>
        </div>
      </form>
    </Dialog>
  );
}

// ---- Ask for evidence ---------------------------------------------------------------------------------------------
export function EvidenceSheet({ idea, prefill, onClose }: { idea: IdeaSummary; prefill?: string; onClose: () => void }) {
  const toast = useToast();
  const refresh = useRefresh();
  const [q, setQ] = useState(prefill ?? "");
  const [busy, setBusy] = useState(false);
  const ok = words(q) >= 4;
  const go = async () => {
    setBusy(true);
    try { await api.post(`/api/ideas/${idea.id}/evidence-requests`, { question: q.trim(), role: "registrar" }); toast.show("The panel will look into it on the next run."); refresh(); onClose(); }
    catch (e) { toast.show(e instanceof ApiError ? e.detail : "That could not be saved.", { tone: "error", ms: 8000 }); setBusy(false); }
  };
  return (
    <Dialog onClose={onClose} label={`Ask for evidence on ${idea.title}`}>
      <form className="space-y-5 p-6" onSubmit={(e) => { e.preventDefault(); if (ok) void go(); }}>
        <div><p className="text-meta text-ink-2">Ask for evidence</p><h2 className="text-title">{idea.title}</h2></div>
        <p className="text-ink-2">Say what you want to know. The panel works on it at the next run and it comes back to your queue.</p>
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={4} placeholder="What would you need to see?"
          className="w-full rounded border border-rule-strong bg-canvas px-3 py-2 outline-none placeholder:text-ink-2 focus:border-accent" />
        <div className="-mx-6 flex justify-end gap-3 border-t border-rule px-6 pt-4">
          <Button kind="ghost" onClick={onClose}>Cancel</Button><Button type="submit" kind="primary" disabled={!ok || busy}>Ask the panel</Button>
        </div>
      </form>
    </Dialog>
  );
}

// ---- Discuss in Claude: a ready prompt to paste. No strategy text goes into a URL. -----------------------------------
export function ClaudeSheet({ idea, kind, onClose }: { idea: IdeaSummary; kind: "idea" | "objection"; onClose: () => void }) {
  const toast = useToast();
  const prompt = kind === "objection"
    ? `Argue the other side of the objection on "${idea.title}" (${idea.id}), then help me draft a reply.`
    : `Walk me through why the panel scored "${idea.title}" (${idea.id}) the way it did, and where I might disagree.`;
  return (
    <Dialog onClose={onClose} label="Discuss in Claude">
      <div className="space-y-4 p-6">
        <h2 className="text-title">Discuss in Claude</h2>
        <p className="text-ink-2">Claude reads the ledger through the same connector. Paste this into a conversation with Gatekeeper connected.</p>
        <p className="serif rounded border border-rule bg-sunken p-4 text-lead">{prompt}</p>
        <div className="flex justify-end gap-3">
          <Button kind="ghost" onClick={onClose}>Close</Button>
          <Button kind="primary" onClick={async () => { await navigator.clipboard?.writeText(prompt); toast.show("Copied."); onClose(); }}>Copy prompt</Button>
        </div>
      </div>
    </Dialog>
  );
}

export const hintFor = (idea: IdeaSummary) => defaultSentence(idea.queue);
