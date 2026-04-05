import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Layout } from "@/components/Layout";
import { BriefingPage } from "@/pages/BriefingPage";
import { PlayersPage } from "@/pages/PlayersPage";
import { FixturesPage } from "@/pages/FixturesPage";
import { TransfersPage } from "@/pages/TransfersPage";
import { TeamsPage } from "@/pages/TeamsPage";
import { TrendsPage } from "@/pages/TrendsPage";

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<BriefingPage />} />
            <Route path="players" element={<PlayersPage />} />
            <Route path="fixtures" element={<FixturesPage />} />
            <Route path="transfers" element={<TransfersPage />} />
            <Route path="teams" element={<TeamsPage />} />
            <Route path="trends" element={<TrendsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
