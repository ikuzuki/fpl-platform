import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Layout } from "@/components/Layout";
import { BriefingPage } from "@/pages/BriefingPage";
import { PlayersPage } from "@/pages/players/PlayersPage";
import { FixturesPage } from "@/pages/FixturesPage";
import { TransfersPage } from "@/pages/TransfersPage";
import { TeamsPage } from "@/pages/TeamsPage";
import { TrendsPage } from "@/pages/trends/TrendsPage";
import { CaptainPage } from "@/pages/CaptainPage";
import { DifferentialsPage } from "@/pages/DifferentialsPage";
import { PlannerPage } from "@/pages/PlannerPage";
import { AboutPage } from "@/pages/AboutPage";
import { ChatPage } from "@/pages/chat/ChatPage";

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
            <Route path="captain" element={<CaptainPage />} />
            <Route path="differentials" element={<DifferentialsPage />} />
            <Route path="planner" element={<PlannerPage />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="about" element={<AboutPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
