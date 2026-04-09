import { createBrowserRouter, RouterProvider } from "react-router-dom";

import AppShell from "./components/AppShell";
import EvolutionArena from "./components/EvolutionArena";
import EvolutionDashboard from "./components/EvolutionDashboard";
import SkillExportPreview from "./components/SkillExportPreview";
import SpecializationInput from "./components/SpecializationInput";

function ComingSoon({ title }: { title: string }) {
  return (
    <div className="mx-auto max-w-[1400px] px-6 py-24 text-center">
      <h1 className="font-display text-4xl tracking-tight">{title}</h1>
      <p className="mt-4 text-on-surface-dim">Coming in v1.1.</p>
    </div>
  );
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <EvolutionDashboard /> },
      { path: "new", element: <SpecializationInput /> },
      { path: "runs/:runId", element: <EvolutionArena /> },
      { path: "runs/:runId/export", element: <SkillExportPreview /> },
      { path: "registry", element: <ComingSoon title="Evolved Skills Registry" /> },
      { path: "bible", element: <ComingSoon title="The Claude Skills Bible" /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
