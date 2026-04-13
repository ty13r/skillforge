import { createBrowserRouter, RouterProvider } from "react-router-dom";

import AgentRegistry from "./components/AgentRegistry";
import AppShell from "./components/AppShell";
import BibleBrowser from "./components/BibleBrowser";
import EvolutionArena from "./components/EvolutionArena";
import EvolutionDashboard from "./components/EvolutionDashboard";
import SeedDetailView from "./components/SeedDetailView";
import SkillDiffViewer from "./components/SkillDiffViewer";
import SkillExportPreview from "./components/SkillExportPreview";
import JournalBrowser from "./components/JournalBrowser";
import SkldBench from "./components/SkldBench";
import SkldBenchFamily from "./components/SkldBenchFamily";
import SpecializationInput from "./components/SpecializationInput";
import TaxonomyBrowser from "./components/TaxonomyBrowser";

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <EvolutionDashboard /> },
      { path: "new", element: <SpecializationInput /> },
      { path: "runs/:runId", element: <EvolutionArena /> },
      { path: "runs/:runId/export", element: <SkillExportPreview /> },
      { path: "runs/:runId/diff", element: <SkillDiffViewer /> },
      { path: "runs/:runId/skills/:skillId", element: <SeedDetailView /> },
      { path: "registry", element: <AgentRegistry /> },
      { path: "bench", element: <SkldBench /> },
      { path: "bench/:familySlug", element: <SkldBenchFamily /> },
      { path: "taxonomy", element: <TaxonomyBrowser /> },
      { path: "bible", element: <BibleBrowser /> },
      { path: "journal", element: <JournalBrowser /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
