/**
 * React Query hooks for /api/runs/* endpoints.
 *
 * One hook per endpoint. See docs/clean-code.md §8 — no raw fetch()
 * in components, no manual useEffect chains for data-fetching, no
 * custom loading/error/retry logic. React Query owns all of that.
 */

import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/api/client";
import type {
  BenchFamilyDetail,
  DimensionStatus,
  LineageEdge,
  LineageNode,
  RunDetail,
  RunReport,
  Variant,
} from "@/types";

interface LineagePayload {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

const runKey = (runId: string) => ["run", runId] as const;

export function useRun(runId: string | null) {
  return useQuery({
    queryKey: runKey(runId ?? "").concat("detail") as readonly unknown[],
    queryFn: () => apiClient.get<RunDetail>(`/api/runs/${runId}`),
    enabled: !!runId,
  });
}

export function useRunReport(runId: string | null) {
  return useQuery({
    queryKey: [...runKey(runId ?? ""), "report"],
    queryFn: () => apiClient.get<RunReport>(`/api/runs/${runId}/report`),
    enabled: !!runId,
  });
}

export function useRunDimensions(
  runId: string | null,
  opts: { refetchInterval?: number | false } = {},
) {
  return useQuery({
    queryKey: [...runKey(runId ?? ""), "dimensions"],
    queryFn: () => apiClient.get<DimensionStatus[]>(`/api/runs/${runId}/dimensions`),
    enabled: !!runId,
    refetchInterval: opts.refetchInterval ?? false,
  });
}

export function useRunLineage(runId: string | null) {
  return useQuery({
    queryKey: [...runKey(runId ?? ""), "lineage"],
    queryFn: () => apiClient.get<LineagePayload>(`/api/runs/${runId}/lineage`),
    enabled: !!runId,
  });
}

export function useRunSkillMd(runId: string | null) {
  return useQuery({
    queryKey: [...runKey(runId ?? ""), "skill_md"],
    queryFn: () => apiClient.getText(`/api/runs/${runId}/export?format=skill_md`),
    enabled: !!runId,
  });
}

export function useFamilyVariants(familyId: string | null | undefined) {
  return useQuery({
    queryKey: ["family", familyId, "variants"] as const,
    queryFn: () => apiClient.get<Variant[]>(`/api/families/${familyId}/variants`),
    enabled: !!familyId,
  });
}

export function useBenchFamily(slug: string | null | undefined) {
  return useQuery({
    queryKey: ["bench", slug] as const,
    queryFn: () => apiClient.get<BenchFamilyDetail>(`/api/bench/${slug}`),
    enabled: !!slug,
  });
}
