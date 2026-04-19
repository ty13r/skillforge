import { useRef, useState } from "react";

interface UploadResponse {
  upload_id: string | null;
  filename: string;
  valid: boolean;
  frontmatter?: Record<string, unknown>;
  skill_md_content?: string;
  supporting_files?: string[];
  errors?: string[];
}

interface SkillUploaderProps {
  onUploadReady: (upload: UploadResponse) => void;
  current: UploadResponse | null;
}

export default function SkillUploader({ onUploadReady, current }: SkillUploaderProps) {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/uploads/skill", { method: "POST", body: form });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as UploadResponse;
      onUploadReady(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  if (current?.valid) {
    return (
      <div className="rounded-xl border border-tertiary/40 bg-tertiary/5 p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-tertiary">
              ✓ Valid SKILL.md
            </p>
            <p className="mt-1 font-display text-lg tracking-tight">
              {String(current.frontmatter?.name ?? current.filename)}
            </p>
            <p className="mt-1 max-w-2xl text-xs text-on-surface-dim">
              {String(current.frontmatter?.description ?? "").slice(0, 200)}
            </p>
            {current.supporting_files && current.supporting_files.length > 0 && (
              <p className="mt-2 font-mono text-[0.625rem] text-on-surface-dim">
                + {current.supporting_files.length} supporting file
                {current.supporting_files.length === 1 ? "" : "s"}
              </p>
            )}
          </div>
          <button
            onClick={() => {
              onUploadReady({
                upload_id: null,
                filename: "",
                valid: false,
              });
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim hover:text-on-surface"
          >
            Replace
          </button>
        </div>
      </div>
    );
  }

  if (current && !current.valid && current.errors) {
    return (
      <div className="space-y-3">
        <div className="rounded-xl border border-error/40 bg-error/5 p-5">
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-error">
            ✕ Validation failed
          </p>
          <ul className="mt-2 space-y-1 text-sm text-error">
            {current.errors.map((e, i) => (
              <li key={i}>• {e}</li>
            ))}
          </ul>
        </div>
        <button
          onClick={() => {
            onUploadReady({ upload_id: null, filename: "", valid: false });
            if (inputRef.current) inputRef.current.value = "";
          }}
          className="text-sm text-on-surface-dim hover:text-on-surface"
        >
          Try a different file →
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragActive(true);
      }}
      onDragLeave={() => setDragActive(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
        dragActive
          ? "border-primary bg-primary/5"
          : "border-outline-variant bg-surface-container-lowest hover:border-primary/50"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".md,.zip"
        onChange={handleChange}
        className="hidden"
      />
      {uploading ? (
        <p className="text-on-surface-dim">Uploading…</p>
      ) : (
        <>
          <p className="font-display text-xl tracking-tight">Drop a SKILL.md or .zip here</p>
          <p className="mt-2 text-sm text-on-surface-dim">
            or click to browse · max 1 MB · validates against bible patterns
          </p>
        </>
      )}
      {error && <p className="mt-3 font-mono text-xs text-error">{error}</p>}
    </div>
  );
}
