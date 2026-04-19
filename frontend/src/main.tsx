import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./index.css";

// Defaults tuned for SKLD's live-run UI: the WebSocket channel is the
// real-time source of truth, so we don't need aggressive background
// refetch. Disable window-focus refetch to avoid hammering the API
// whenever the user Cmd-Tabs. Keep retry at 1 — transient network
// blips should not surface as a hard failure state, but a broken
// endpoint shouldn't keep retrying for a minute either.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>,
);
