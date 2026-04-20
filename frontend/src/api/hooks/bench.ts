/** React Query hook for the SKLD-bench summary endpoint. */
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import type { BenchSummary } from "@/types";

export function useBenchSummary() {
  return useQuery({
    queryKey: ["bench", "summary"] as const,
    queryFn: () => apiClient.get<BenchSummary>("/api/bench/summary"),
  });
}
