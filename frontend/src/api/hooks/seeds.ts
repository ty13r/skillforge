/**
 * React Query hooks for /api/seeds (the curated seed-library registry).
 *
 * See docs/clean-code.md §8 — no raw fetch() in components.
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";

import type { SeedSummary } from "@/components/specializationInput/types";

export function useSeeds() {
  return useQuery({
    queryKey: ["seeds"] as const,
    queryFn: () => apiClient.get<SeedSummary[]>("/api/seeds"),
  });
}
