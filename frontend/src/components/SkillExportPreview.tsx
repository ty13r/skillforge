import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import type { RunDetail } from "../types";

export default function SkillExportPreview() {
  const { runId } = useParams<{ runId: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [skillMd, setSkillMd] = useState<string>("");
  const [sdkConfig, setSdkConfig] = useState<string>("");

  useEffect(() => {
    if (!runId) return;
    fetch(`/api/runs/${runId}`)
      .then((r) => r.json())
      .then(setRun);
    fetch(`/api/runs/${runId}/export?format=skill_md`)
      .then((r) => r.text())
      .then(setSkillMd)
      .catch(() => undefined);
    fetch(`/api/runs/${runId}/export?format=agent_sdk_config`)
      .then((r) => r.text())
      .then(setSdkConfig)
      .catch(() => undefined);
  }, [runId]);

  if (!runId) return null;

  const downloadHref = `/runs/${runId}/export?format=skill_dir`;

  return (
    <div className="mx-auto max-w-[1400px] px-6 py-10">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Build ID: {runId.slice(0, 8)} // Stable Diffusion v3
          </p>
          <h1 className="mt-2 font-display text-4xl tracking-tight">
            Export: {run?.specialization?.slice(0, 60) ?? "..."}
          </h1>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="rounded-xl bg-surface-container-low p-5">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Skill Directory
          </p>
          <h3 className="mt-1 font-display text-lg tracking-tight">Compressed Binary Structure</h3>
          <pre className="mt-4 max-h-64 overflow-y-auto rounded-xl bg-surface-container-lowest p-3 font-mono text-xs text-on-surface-dim">
            {skillMd ? skillMd.slice(0, 800) + (skillMd.length > 800 ? "\n..." : "") : "(loading)"}
          </pre>
          <a
            href={downloadHref}
            className="mt-4 block rounded-xl bg-surface-container-high p-3 text-center text-sm text-on-surface transition-colors hover:bg-surface-bright"
          >
            ↓ Download .zip
          </a>
        </div>

        <div className="rounded-xl bg-surface-container-low p-5">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Agent SDK Config
          </p>
          <h3 className="mt-1 font-display text-lg tracking-tight">Skill Schema Definition</h3>
          <pre className="mt-4 max-h-64 overflow-y-auto rounded-xl bg-surface-container-lowest p-3 font-mono text-xs text-on-surface-dim">
            {sdkConfig
              ? sdkConfig.slice(0, 800) + (sdkConfig.length > 800 ? "\n..." : "")
              : "(loading)"}
          </pre>
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(sdkConfig)}
            className="mt-4 block w-full rounded-xl bg-primary-gradient p-3 text-center text-sm font-medium text-surface-container-lowest"
          >
            Copy JSON
          </button>
        </div>

        <div className="rounded-xl bg-surface-container-low p-5">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            Deployment
          </p>
          <h3 className="mt-1 font-display text-lg tracking-tight">Terminal Protocols</h3>
          <div className="mt-4 rounded-xl bg-surface-container-lowest p-3 font-mono text-xs text-on-surface-dim">
            <p className="text-on-surface">Claude Code</p>
            <pre className="mt-1">unzip skill.zip -d ~/.claude/skills/</pre>
          </div>
          <div className="mt-2 flex items-center justify-between font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
            <span>Compatibility</span>
            <span className="text-tertiary">96.2% Match</span>
          </div>
        </div>
      </div>
    </div>
  );
}
