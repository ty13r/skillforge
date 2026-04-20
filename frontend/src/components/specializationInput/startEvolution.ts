/**
 * Pure API-call dispatcher for POSTing to /api/evolve or /api/evolve/from-parent.
 *
 * Takes the flattened form state and returns the new run id. All three
 * source modes (scratch, upload, fork) funnel through here so the UI
 * component only cares about UI state + one submit call.
 */

import { apiClient } from "@/api/client";
import type { EvolveResponse } from "@/types";

import type { GeneratedPackage, SourceMode, UploadResponse } from "./types";

export interface StartEvolutionInput {
  sourceMode: SourceMode;
  specialization: string;
  populationSize: number;
  numGenerations: number;
  budget: number;
  evolutionMode: "auto" | "atomic" | "molecular";
  inviteCode: string | null;
  upload: UploadResponse | null;
  forkedSeedId: string | null;
  generatedPackage: GeneratedPackage | null;
}

export async function startEvolution(input: StartEvolutionInput): Promise<string> {
  const {
    sourceMode,
    specialization,
    populationSize,
    numGenerations,
    budget,
    evolutionMode,
    inviteCode,
    upload,
    forkedSeedId,
    generatedPackage,
  } = input;

  const baseParams = {
    population_size: populationSize,
    num_generations: numGenerations,
    max_budget_usd: budget,
    invite_code: inviteCode ?? undefined,
  };

  if (sourceMode === "scratch") {
    if (!specialization.trim() && !generatedPackage) {
      throw new Error("Specialization is required");
    }
    if (generatedPackage) {
      const resp = await apiClient.post<EvolveResponse>("/api/evolve/from-parent", {
        parent_source: "generated",
        skill_md_content: generatedPackage.skillMdContent,
        supporting_files: generatedPackage.supportingFiles,
        specialization: generatedPackage.specialization || specialization,
        ...baseParams,
      });
      return resp.run_id;
    }
    const resp = await apiClient.post<EvolveResponse>("/api/evolve", {
      mode: "domain",
      specialization,
      ...baseParams,
      // "auto" maps to undefined so the Taxonomist decides server-side.
      evolution_mode: evolutionMode === "auto" ? undefined : evolutionMode,
    });
    return resp.run_id;
  }

  if (sourceMode === "upload") {
    if (!upload?.upload_id) {
      throw new Error("Upload a valid SKILL.md or zip first");
    }
    const resp = await apiClient.post<EvolveResponse>("/api/evolve/from-parent", {
      parent_source: "upload",
      parent_id: upload.upload_id,
      specialization: specialization || undefined,
      ...baseParams,
    });
    return resp.run_id;
  }

  // fork
  if (!forkedSeedId) {
    throw new Error("No seed selected to fork");
  }
  const resp = await apiClient.post<EvolveResponse>("/api/evolve/from-parent", {
    parent_source: "registry",
    parent_id: forkedSeedId,
    specialization: specialization || undefined,
    ...baseParams,
  });
  return resp.run_id;
}
