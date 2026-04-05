import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { PlayersPage } from "@/pages/PlayersPage";
import { FixturesPage } from "@/pages/FixturesPage";
import { TransfersPage } from "@/pages/TransfersPage";
import { TeamsPage } from "@/pages/TeamsPage";
import { TrendsPage } from "@/pages/TrendsPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<PlayersPage />} />
          <Route path="fixtures" element={<FixturesPage />} />
          <Route path="transfers" element={<TransfersPage />} />
          <Route path="teams" element={<TeamsPage />} />
          <Route path="trends" element={<TrendsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
