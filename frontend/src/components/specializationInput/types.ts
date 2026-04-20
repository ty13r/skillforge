/** Shared types for the SpecializationInput view. */

export type SourceMode = "scratch" | "upload" | "fork";

export type EvolutionMode = "auto" | "atomic" | "molecular";

export interface UploadResponse {
  upload_id: string | null;
  filename: string;
  valid: boolean;
  frontmatter?: Record<string, unknown>;
  skill_md_content?: string;
  supporting_files?: string[];
  errors?: string[];
}

export interface SeedSummary {
  id: string;
  title: string;
  description: string;
  category: string;
  difficulty: "easy" | "medium" | "hard";
}

export interface GeneratedPackage {
  skillMdContent: string;
  supportingFiles: Record<string, string>;
  specialization: string;
}

export const DIFFICULTY_COLOR: Record<string, string> = {
  easy: "text-tertiary",
  medium: "text-warning",
  hard: "text-error",
};
