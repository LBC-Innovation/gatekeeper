import { useEffect, useRef } from "react";

const typing = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName?.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || el.isContentEditable;
};

/** Register single-key shortcuts for a screen. Ignored while typing, with modifiers held, or while a dialog is open. */
export function useHotkeys(map: Record<string, (e: KeyboardEvent) => void>, enabled = true) {
  const ref = useRef(map);
  ref.current = map;
  useEffect(() => {
    if (!enabled) return;
    const on = (e: KeyboardEvent) => {
      if (typing(e.target) || e.metaKey || e.ctrlKey || document.querySelector("[role=dialog]")) return;
      const key = (e.altKey ? "Alt+" : "") + e.key;
      const fn = ref.current[key];
      if (fn) { e.preventDefault(); fn(e); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, [enabled]);
}
