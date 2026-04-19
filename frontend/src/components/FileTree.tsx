import { useMemo, useState } from "react";

interface FileTreeProps {
  files: string[];
  selected: string;
  onSelect: (path: string) => void;
}

interface TreeNode {
  name: string;
  path: string; // full path for leaf nodes
  isDir: boolean;
  children: TreeNode[];
}

function buildTree(paths: string[]): TreeNode[] {
  const root: TreeNode[] = [];

  for (const path of paths) {
    const parts = path.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      const isLast = i === parts.length - 1;
      const existing = current.find((n) => n.name === name);

      if (existing) {
        current = existing.children;
      } else {
        const node: TreeNode = {
          name,
          path: isLast ? path : parts.slice(0, i + 1).join("/"),
          isDir: !isLast,
          children: [],
        };
        current.push(node);
        current = node.children;
      }
    }
  }

  // Sort: directories first, then files, alphabetical within each group
  const sortNodes = (nodes: TreeNode[]): TreeNode[] => {
    nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    for (const n of nodes) {
      if (n.children.length > 0) sortNodes(n.children);
    }
    return nodes;
  };

  return sortNodes(root);
}

function TreeNodeRow({
  node,
  depth,
  selected,
  onSelect,
  expanded,
  onToggle,
}: {
  node: TreeNode;
  depth: number;
  selected: string;
  onSelect: (path: string) => void;
  expanded: Set<string>;
  onToggle: (path: string) => void;
}) {
  const isOpen = expanded.has(node.path);
  const isSelected = !node.isDir && node.path === selected;
  const indent = depth * 16;

  return (
    <>
      {node.isDir ? (
        <button
          onClick={() => onToggle(node.path)}
          className="flex w-full items-center gap-1 rounded px-1 py-1 text-left font-mono text-[0.6875rem] text-on-surface-dim transition-colors hover:text-on-surface"
          style={{ paddingLeft: `${indent + 4}px` }}
        >
          <span className="w-4 text-center text-[0.625rem]">{isOpen ? "▾" : "▸"}</span>
          <span className="text-[0.625rem]">📁</span>
          <span>{node.name}/</span>
        </button>
      ) : (
        <button
          onClick={() => onSelect(node.path)}
          className={`flex w-full items-center gap-1 rounded px-1 py-1 text-left font-mono text-[0.6875rem] transition-colors ${
            isSelected
              ? "bg-primary/10 text-primary"
              : "hover:bg-surface-container-mid text-on-surface-dim hover:text-on-surface"
          }`}
          style={{ paddingLeft: `${indent + 4}px` }}
          title={node.path}
        >
          <span className="w-4 text-center text-[0.625rem]">{fileIcon(node.name)}</span>
          <span className="truncate">{node.name}</span>
        </button>
      )}

      {node.isDir &&
        isOpen &&
        node.children.map((child) => (
          <TreeNodeRow
            key={child.path}
            node={child}
            depth={depth + 1}
            selected={selected}
            onSelect={onSelect}
            expanded={expanded}
            onToggle={onToggle}
          />
        ))}
    </>
  );
}

function fileIcon(name: string): string {
  if (name.endsWith(".py")) return "🐍";
  if (name.endsWith(".sh") || name.endsWith(".bash")) return "⚙";
  if (name.endsWith(".md")) return "📄";
  if (name.endsWith(".json")) return "{ }";
  if (name.endsWith(".yaml") || name.endsWith(".yml")) return "📋";
  if (name.endsWith(".tf") || name.endsWith(".hcl")) return "🏗";
  if (name.endsWith(".ts") || name.endsWith(".tsx")) return "TS";
  if (name.endsWith(".js") || name.endsWith(".jsx")) return "JS";
  if (name.endsWith(".css")) return "🎨";
  if (name.endsWith(".html")) return "🌐";
  if (name.endsWith(".sql")) return "🗃";
  if (name === "Dockerfile" || name.endsWith(".dockerfile")) return "🐳";
  return "📄";
}

export default function FileTree({ files, selected, onSelect }: FileTreeProps) {
  const tree = useMemo(() => buildTree(files), [files]);

  // Start with all directories expanded
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const dirs = new Set<string>();
    for (const path of files) {
      const parts = path.split("/");
      for (let i = 1; i < parts.length; i++) {
        dirs.add(parts.slice(0, i).join("/"));
      }
    }
    return dirs;
  });

  const toggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  return (
    <div className="space-y-0.5">
      {tree.map((node) => (
        <TreeNodeRow
          key={node.path}
          node={node}
          depth={0}
          selected={selected}
          onSelect={onSelect}
          expanded={expanded}
          onToggle={toggle}
        />
      ))}
    </div>
  );
}
