// WebSocket hook for real-time evolution events — Step 10.
import { useEffect, useState } from "react";

export interface EvolutionEvent {
  event: string;
  [key: string]: unknown;
}

export function useEvolutionSocket(runId: string | null) {
  const [events, setEvents] = useState<EvolutionEvent[]>([]);

  useEffect(() => {
    if (!runId) return;
    // Real WebSocket connection wired in Step 10.
  }, [runId]);

  return { events };
}
