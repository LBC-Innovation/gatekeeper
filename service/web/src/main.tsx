import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { ApiError } from "./api/client";
import { Shell } from "./Shell";
import Compare from "./screens/Compare";
import Guide from "./screens/Guide";
import IdeaRecord from "./screens/IdeaRecord";
import Ideas from "./screens/Ideas";
import Log from "./screens/Log";
import Portfolio from "./screens/Portfolio";
import Runs from "./screens/Runs";
import Settings from "./screens/Settings";
import Signals from "./screens/Signals";
import Team from "./screens/Team";
import Today from "./screens/Today";
import "./index.css";

const qc = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 5_000, refetchOnWindowFocus: true, retry: (n, e) => !(e instanceof ApiError && e.status < 500) && n < 2 },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Navigate to="/today" replace />} />
            <Route path="today" element={<Today />} />
            <Route path="ideas" element={<Ideas />} />
            <Route path="ideas/:id" element={<IdeaRecord />} />
            <Route path="compare" element={<Compare />} />
            <Route path="log" element={<Log />} />
            <Route path="team" element={<Team />} />
            <Route path="how-it-works" element={<Guide />} />
            <Route path="portfolio" element={<Portfolio />} />
            <Route path="settings/:tab?" element={<Settings />} />
            <Route path="runs/:id?" element={<Runs />} />
            <Route path="signals/:id?" element={<Signals />} />
            <Route path="*" element={<Navigate to="/today" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
