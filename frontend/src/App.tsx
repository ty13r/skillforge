import { createBrowserRouter, RouterProvider } from "react-router-dom";

import AgentRegistry from "./components/AgentRegistry";
import AppShell from "./components/AppShell";
import BibleBrowser from "./components/BibleBrowser";
import EvolutionArena from "./components/EvolutionArena";
import EvolutionDashboard from "./components/EvolutionDashboard";
import SeedDetailView from "./components/SeedDetailView";
import SkillDiffViewer from "./components/SkillDiffViewer";
import SkillExportPreview from "./components/SkillExportPreview";
import SpecializationInput from "./components/SpecializationInput";

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
      { path: "bible", element: <BibleBrowser /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
