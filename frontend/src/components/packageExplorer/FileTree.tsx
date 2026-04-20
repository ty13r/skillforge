/**
 * Collapsible file tree for a PackageExplorer section.
 *
 * Groups files under their top-level subdirectory so ``scripts/*`` and
 * ``references/*`` render as collapsible directory groups; standalone
 * top-level files render above the directory groups. Pure presentational
 * component — no fetches, no side effects beyond the open/closed state.
 */
import { useMemo, useState } from "react";

import type { VirtualFile } from "./types";

interface FileRowProps {
  file: VirtualFile;
  selected: boolean;
  onSelect: () => void;
  indent?: number;
}

function FileRow({ file, selected, onSelect, indent = 0 }: FileRowProps) {
  const basename = file.path.split("/").pop() ?? file.path;
  const icon = basename.endsWith(".json") ? "{ }" : "📄";
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-[0.6875rem] transition-colors ${
        selected
          ? "bg-tertiary/10 text-tertiary"
          : "text-on-surface-dim hover:bg-surface-container-high hover:text-on-surface"
      }`}
      style={{ paddingLeft: `${8 + indent * 12}px` }}
      title={file.path}
    >
      <span className="w-4 shrink-0 text-center text-[0.625rem]">{icon}</span>
      <span className="truncate">{basename}</span>
    </button>
  );
}

interface FileTreeProps {
  files: VirtualFile[];
  selectedPath: string;
  onSelect: (path: string) => void;
  /** Optional path prefix to strip before grouping (e.g. ``"_meta/"``). */
  stripPrefix?: string;
  /** Whether directories start expanded (true) or collapsed (false). */
  defaultOpen?: boolean;
}

export default function FileTree({
  files,
  selectedPath,
  onSelect,
  stripPrefix = "",
  defaultOpen = true,
}: FileTreeProps) {
  const { topLevel, dirs, allDirNames } = useMemo(() => {
    const top: VirtualFile[] = [];
    const grouped = new Map<string, VirtualFile[]>();
    const dirNames: string[] = [];
    for (const f of files) {
      const rest = stripPrefix ? f.path.replace(new RegExp(`^${stripPrefix}`), "") : f.path;
      if (!rest.includes("/")) {
        top.push(f);
      } else {
        const dirName = rest.split("/")[0];
        if (!grouped.has(dirName)) {
          grouped.set(dirName, []);
          dirNames.push(dirName);
        }
        grouped.get(dirName)!.push(f);
      }
    }
    return { topLevel: top, dirs: grouped, allDirNames: dirNames };
  }, [files, stripPrefix]);

  const [openDirs, setOpenDirs] = useState<Set<string>>(() =>
    defaultOpen ? new Set(allDirNames) : new Set(),
  );

  const toggle = (dir: string) => {
    setOpenDirs((prev) => {
      const next = new Set(prev);
      if (next.has(dir)) next.delete(dir);
      else next.add(dir);
      return next;
    });
  };

  return (
    <div className="space-y-0.5">
      {topLevel.map((f) => (
        <FileRow
          key={f.path}
          file={f}
          selected={selectedPath === f.path}
          onSelect={() => onSelect(f.path)}
        />
      ))}
      {Array.from(dirs.entries()).map(([dir, dirFiles]) => {
        const isOpen = openDirs.has(dir);
        return (
          <div key={dir}>
            <button
              type="button"
              onClick={() => toggle(dir)}
              className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left font-mono text-[0.6875rem] text-on-surface-dim transition-colors hover:text-on-surface"
              style={{ paddingLeft: "8px" }}
            >
              <span className="w-4 text-center text-[0.625rem]">{isOpen ? "▾" : "▸"}</span>
              <span className="text-[0.625rem]">📁</span>
              <span>
                {dir}/ · {dirFiles.length}
              </span>
            </button>
            {isOpen &&
              dirFiles.map((f) => (
                <FileRow
                  key={f.path}
                  file={f}
                  selected={selectedPath === f.path}
                  onSelect={() => onSelect(f.path)}
                  indent={1}
                />
              ))}
          </div>
        );
      })}
    </div>
  );
}
