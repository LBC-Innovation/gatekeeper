import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { IdeaRecord, IdeaSummary, Objection, Verb } from "../api/types";
import { useToast } from "../ui/toast";
import { AnswerSheet, ClaudeSheet, DecisionSheet, EvidenceSheet } from "./Sheets";

type Sheet =
  | { t: "decide"; idea: IdeaSummary; verb: Verb | null }
  | { t: "answer"; idea: IdeaSummary; objection: Objection }
  | { t: "evidence"; idea: IdeaSummary; prefill?: string }
  | { t: "claude"; idea: IdeaSummary; kind: "idea" | "objection" };

interface ActionsApi {
  decide: (idea: IdeaSummary, verb?: Verb | null) => void;
  answer: (idea: IdeaSummary, objection?: Objection) => void;
  evidence: (idea: IdeaSummary, prefill?: string) => void;
  claude: (idea: IdeaSummary, kind?: "idea" | "objection") => void;
}
const Ctx = createContext<ActionsApi>({ decide() {}, answer() {}, evidence() {}, claude() {} });
export const useActions = () => useContext(Ctx);

/** Every screen opens the same four sheets. They live here, so a shortcut works wherever you are. */
export function ActionsProvider({ children }: { children: ReactNode }) {
  const [sheet, setSheet] = useState<Sheet | null>(null);
  const qc = useQueryClient();
  const toast = useToast();
  const api_ = useMemo<ActionsApi>(() => ({
    decide: (idea, verb = null) => { if (!idea.decision) setSheet({ t: "decide", idea, verb }); },
    answer: async (idea, objection) => {
      let o = objection;
      if (!o) {
        const rec = await qc.fetchQuery({ queryKey: ["idea", idea.id], queryFn: () => api.get<IdeaRecord>(`/api/ideas/${idea.id}`) });
        o = rec.objections.find((x) => x.status === "open");
      }
      if (o) setSheet({ t: "answer", idea, objection: o }); else toast.show("There is no open objection to answer.");
    },
    evidence: (idea, prefill) => setSheet({ t: "evidence", idea, prefill }),
    claude: (idea, kind = "idea") => setSheet({ t: "claude", idea, kind }),
  }), [qc, toast]);
  const close = () => setSheet(null);
  return (
    <Ctx.Provider value={api_}>
      {children}
      {sheet?.t === "decide" && <DecisionSheet idea={sheet.idea} initial={sheet.verb} onClose={close} />}
      {sheet?.t === "answer" && <AnswerSheet idea={sheet.idea} objection={sheet.objection} onClose={close} />}
      {sheet?.t === "evidence" && <EvidenceSheet idea={sheet.idea} prefill={sheet.prefill} onClose={close} />}
      {sheet?.t === "claude" && <ClaudeSheet idea={sheet.idea} kind={sheet.kind} onClose={close} />}
    </Ctx.Provider>
  );
}
