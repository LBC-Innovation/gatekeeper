import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { useBoard, useInbox, useLedgerStream } from "./api/hooks";
import { api } from "./api/client";
import { ActionsProvider } from "./components/Actions";
import { RefProvider } from "./components/RefDialog";
import { CommandPalette } from "./components/CommandPalette";
import { fmtTime } from "./lib/text";
import { Button } from "./ui/primitives";
import { ToastProvider, useToast } from "./ui/toast";

const STAGE_LABEL: Record<string, string> = {
  scout: "scouting", curate: "curating", frame: "framing problems", invent: "drafting ideas", gate: "first screen", panel: "the panel is reviewing",
  round2: "round 2", resolve: "ranking", brief: "writing the brief", calibrate: "calibrating",
};

function SignIn() {
  return (
    <div className="mx-auto max-w-[560px] px-6 py-24">
      <h1 className="text-display">Sign in</h1>
      <p className="mt-3 text-ink-2">Gatekeeper opens from a one-time link, so there is no password to remember. Run this in a terminal, then open the link it prints.</p>
      <pre className="mt-4 overflow-x-auto rounded border border-rule bg-sunken p-4 font-mono text-meta">service/dev.sh open</pre>
      <p className="mt-4 text-meta text-ink-2">If the service is not running yet, start it with <span className="font-mono">service/dev.sh</span>. It prints a link when it starts.</p>
    </div>
  );
}

function Frame() {
  const loc = useLocation();
  const toast = useToast();
  const inbox = useInbox();
  const board = useBoard();
  const [palette, setPalette] = useState(false);
  const [gear, setGear] = useState(false);
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute("data-theme") ?? "light");
  const toggleTheme = useCallback(() => {
    const t = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", t);
    try { localStorage.setItem("gk-theme", t); } catch { /* private window */ }
    setTheme(t);
  }, []);
  useLedgerStream((e) => { if (e.event === "run_finished") toast.show("A run finished. The board is up to date."); });
  useEffect(() => { setGear(false); window.scrollTo(0, 0); }, [loc.pathname]);
  useEffect(() => {
    const on = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette(true); } };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  const waiting = (inbox.data?.items ?? []).filter((i) => !i.idea.decision).length;
  const live = inbox.data?.live_run;
  const running = live?.stages.find((s) => s.status === "running") ?? live?.stages[live.stages.length - 1];
  const nav = [["/today", "Today", waiting || null], ["/ideas", "Ideas", null], ["/log", "Log", null]] as const;
  const about = [["/team", "Team"], ["/how-it-works", "How it works"]] as const;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-20 border-b border-rule bg-canvas/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-[1200px] items-center gap-6 px-4 md:px-12">
          <Link to="/today" className="serif text-[20px] leading-none">Gatekeeper</Link>
          <nav aria-label="Primary" className="hidden md:block">
            <ul className="flex items-center gap-1">
              {nav.map(([to, label, n]) => (
                <li key={to}><NavLink to={to} className={({ isActive }) => `inline-flex h-9 items-center rounded px-3 ${isActive ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}>{label}{n ? <span className="ml-2 font-normal text-ink-2 tnum">{n}</span> : null}</NavLink></li>
              ))}
              <li aria-hidden className="mx-2 h-5 w-px bg-rule-strong" />
              {about.map(([to, label]) => (
                <li key={to}><NavLink to={to} className={({ isActive }) => `inline-flex h-9 items-center rounded px-3 ${isActive ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"}`}>{label}</NavLink></li>
              ))}
            </ul>
          </nav>
          <span className="flex-1" />
          <button onClick={() => setPalette(true)} className="hidden h-9 items-center gap-2 rounded px-3 text-ink-2 hover:bg-sunken hover:text-ink md:inline-flex" aria-label="Search or jump">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
            <span>Search</span><span className="kbd">⌘K</span>
          </button>
          <div className="relative">
            <button onClick={() => setGear((g) => !g)} aria-expanded={gear} aria-label="More: portfolio, settings, runs" className="inline-flex h-9 w-9 items-center justify-center rounded text-ink-2 hover:bg-sunken hover:text-ink">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></svg>
            </button>
            {gear && (
              <div className="absolute right-0 z-30 mt-2 w-64 rounded-md border border-rule-strong bg-surface py-2 shadow-lg">
                {([["/team", "The team"], ["/how-it-works", "How it works"], ["/portfolio", "Portfolio balance"], ["/settings", "Settings and calibration"], ["/runs", "Pipeline runs"], ["/signals", "Signals"]] as const).map(([to, l]) => <Link key={to} to={to} className="block px-4 py-2 hover:bg-sunken">{l}</Link>)}
                <div className="my-2 border-t border-rule" />
                <button onClick={toggleTheme} className="block w-full px-4 py-2 text-left hover:bg-sunken">Switch to {theme === "dark" ? "light" : "dark"}</button>
                <p className="px-4 pt-2 text-meta text-ink-2">{inbox.data?.last_run ? `Last run finished ${inbox.data.last_run.finished_at ? fmtTime(inbox.data.last_run.finished_at) : "—"}.` : "No runs yet."}</p>
              </div>
            )}
          </div>
        </div>
        {live && (
          <div className="border-t border-rule bg-sunken" role="status">
            <div className="mx-auto flex max-w-[1200px] items-center gap-3 px-4 py-2 text-meta md:px-12">
              <span className="live-dot inline-block h-2 w-2 rounded-full bg-accent" aria-hidden />
              <span><b className="font-semibold">Run {live.id} is in progress.</b> {running ? `Now: ${STAGE_LABEL[running.stage] ?? running.stage}.` : "Starting."} {live.admitted ? `${live.admitted} ideas are with the panel.` : ""} Your board stays as it was until it finishes.</span>
              <Link to="/runs" className="ml-auto text-accent hover:underline">Watch</Link>
            </div>
          </div>
        )}
      </header>
      <main id="main" className="min-w-0 flex-1 pb-20 md:pb-0"><Outlet context={{ board: board.data }} /></main>
      <nav aria-label="Phone" className="fixed inset-x-0 bottom-0 z-30 flex border-t border-rule bg-canvas/95 backdrop-blur md:hidden">
        {nav.map(([to, label]) => <NavLink key={to} to={to} className={({ isActive }) => `h-12 flex-1 text-center leading-[48px] ${isActive ? "font-semibold text-ink" : "text-ink-2"}`}>{label}</NavLink>)}
      </nav>
      {palette && <CommandPalette ideas={board.data?.rows ?? []} onClose={() => setPalette(false)} toggleTheme={toggleTheme} />}
    </div>
  );
}

export function Shell() {
  const [signedOut, setSignedOut] = useState(false);
  const session = useQuery({ queryKey: ["session"], queryFn: () => api.get("/api/session"), retry: false });
  useEffect(() => {
    const on = () => setSignedOut(true);
    window.addEventListener("gk:unauthorized", on);
    return () => window.removeEventListener("gk:unauthorized", on);
  }, []);
  if (signedOut || session.isError) return <SignIn />;
  if (session.isLoading) return <div className="p-12 text-ink-2">Opening…</div>;
  return (
    <ToastProvider>
      <ActionsProvider><RefProvider><Frame /></RefProvider></ActionsProvider>
    </ToastProvider>
  );
}

export { Button };
