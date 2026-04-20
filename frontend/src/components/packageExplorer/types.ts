/**
 * Shared types for the PackageExplorer view.
 *
 * A VirtualFile is a synthesized file entry rendered in the package browser.
 * "installable" files end up in the downloadable zip and are loaded by Claude
 * at runtime; "metadata" files are evolution artifacts kept for audit only.
 */
export type VirtualFile = {
  path: string;
  content: string;
  language: "markdown" | "code";
  kind: "installable" | "metadata";
};

export function detectLanguage(path: string): "markdown" | "code" {
  return path.endsWith(".md") ? "markdown" : "code";
}

export function deriveDimensionFromId(id: string): string {
  let slug = id
    .replace(/^gen_seed_/, "")
    .replace(/_winner$/, "")
    .replace(/^elixir_phoenix_liveview_?/, "");
  slug = slug.replace(/_/g, "-");
  return slug || id;
}
