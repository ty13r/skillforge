import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import CodeViewer from "./CodeViewer";
import FileTree from "./FileTree";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface GeneratedPackage {
  skillMdContent: string;
  supportingFiles: Record<string, string>;
  specialization: string;
}

interface SpecAssistantChatProps {
  onSpecReady: (spec: string) => void;
  onPackageReady?: (pkg: GeneratedPackage) => void;
}

export default function SpecAssistantChat({
  onSpecReady,
  onPackageReady,
}: SpecAssistantChatProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finalized, setFinalized] = useState(false);

  // Package generation state
  const [generating, setGenerating] = useState(false);
  const [generatedPkg, setGeneratedPkg] = useState<{
    skillMdContent: string;
    supportingFiles: Record<string, string>;
    validationPassed: boolean;
    name: string;
  } | null>(null);
  const [genError, setGenError] = useState<string | null>(null);
  const [previewFile, setPreviewFile] = useState<string | null>(null);
  const finalSpecRef = useRef<string>("");

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending, generating]);

  const generatePackage = async (spec: string) => {
    setGenerating(true);
    setGenError(null);
    try {
      const res = await fetch("/api/spec-assistant/generate-skill", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ specialization: spec }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      const data = await res.json();
      setGeneratedPkg({
        skillMdContent: data.skill_md_content,
        supportingFiles: data.supporting_files || {},
        validationPassed: data.validation_passed,
        name: data.name || "generated-skill",
      });
      if (onPackageReady) {
        onPackageReady({
          skillMdContent: data.skill_md_content,
          supportingFiles: data.supporting_files || {},
          specialization: spec,
        });
      }
    } catch (err) {
      setGenError(String(err));
    } finally {
      setGenerating(false);
    }
  };

  const sendMessage = async (history: ChatMessage[]) => {
    setSending(true);
    setError(null);
    try {
      const res = await fetch("/api/spec-assistant/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: history }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      const data = (await res.json()) as {
        message: string;
        final_spec?: string | null;
      };
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.message },
      ]);
      if (data.final_spec) {
        onSpecReady(data.final_spec);
        setFinalized(true);
        finalSpecRef.current = data.final_spec;
        // Auto-generate skill package
        generatePackage(data.final_spec);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setSending(false);
    }
  };

  const open_ = async () => {
    setOpen(true);
    if (messages.length === 0) {
      await sendMessage([]);
    }
  };

  const submit = async () => {
    const text = input.trim();
    if (!text || sending || finalized) return;
    const next: ChatMessage[] = [
      ...messages,
      { role: "user", content: text },
    ];
    setMessages(next);
    setInput("");
    await sendMessage(next);
  };

  const reset = () => {
    setMessages([]);
    setInput("");
    setError(null);
    setFinalized(false);
    setGenerating(false);
    setGeneratedPkg(null);
    setGenError(null);
    setPreviewFile(null);
    finalSpecRef.current = "";
  };

  if (!open) {
    return (
      <div className="mt-3 flex justify-end">
        <button
          onClick={open_}
          className="inline-flex items-center gap-2 rounded-xl border border-secondary/40 bg-secondary/10 px-5 py-2.5 text-sm font-medium text-secondary transition-colors hover:bg-secondary/20"
        >
          ✨ Generate Skill with AI
        </button>
      </div>
    );
  }

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-secondary/20 bg-surface-container-lowest">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-outline-variant px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-xs text-secondary">✨</span>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-secondary">
            Spec Assistant
          </p>
          {finalized && !generating && !generatedPkg && (
            <span className="rounded-full bg-tertiary/15 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              ✓ spec ready
            </span>
          )}
          {generatedPkg && (
            <span className="rounded-full bg-tertiary/15 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              ✓ package ready
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <button
              onClick={reset}
              className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim transition-colors hover:text-on-surface"
            >
              Reset
            </button>
          )}
          <button
            onClick={() => setOpen(false)}
            className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim transition-colors hover:text-on-surface"
          >
            Hide
          </button>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="max-h-80 space-y-3 overflow-y-auto px-4 py-3 text-sm"
      >
        {messages.length === 0 && !sending && (
          <p className="text-on-surface-dim">Starting conversation…</p>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 ${
                msg.role === "user"
                  ? "bg-primary/20 text-on-surface"
                  : "bg-surface-container-low text-on-surface"
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-xl bg-surface-container-low px-3 py-2 text-on-surface-dim">
              <span className="inline-flex items-center gap-1">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary [animation-delay:300ms]" />
              </span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mx-4 mb-2 rounded-lg bg-error/10 p-2 text-xs text-error">
          {error}
        </div>
      )}

      {/* Package generation status */}
      {generating && (
        <div className="mx-4 mb-2 flex items-center gap-2 rounded-lg bg-secondary/5 p-3 text-sm text-secondary">
          <span className="animate-pulse">●</span>
          Generating skill package from your spec...
        </div>
      )}

      {generatedPkg && (
        <div className="mx-4 mb-2 rounded-lg border border-tertiary/30 bg-tertiary/5 p-3">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              {generatedPkg.validationPassed ? "✓" : "⚠"} Skill Package Generated
            </p>
            <span className="font-mono text-[0.625rem] text-on-surface-dim">
              {Object.keys(generatedPkg.supportingFiles).length + 1} files
            </span>
          </div>
          <div className="mt-2">
            <FileTree
              files={["SKILL.md", ...Object.keys(generatedPkg.supportingFiles)]}
              selected={previewFile ?? ""}
              onSelect={(f) => setPreviewFile(previewFile === f ? null : f)}
            />
          </div>

          {/* File preview panel */}
          {previewFile && (
            <div className="mt-2 rounded-lg border border-outline-variant bg-surface-container-lowest">
              <div className="flex items-center justify-between border-b border-outline-variant px-3 py-1.5">
                <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
                  {previewFile}
                </p>
                <button
                  onClick={() => setPreviewFile(null)}
                  className="font-mono text-[0.625rem] text-on-surface-dim hover:text-on-surface"
                >
                  ✕
                </button>
              </div>
              <div className="max-h-72 overflow-y-auto p-3">
                {previewFile === "SKILL.md" ? (
                  <div className="bible-prose text-xs">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {generatedPkg.skillMdContent.replace(/^---\n[\s\S]*?\n---\n?/, "")}
                    </ReactMarkdown>
                  </div>
                ) : previewFile.endsWith(".md") ? (
                  <div className="bible-prose text-xs">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {generatedPkg.supportingFiles[previewFile] ?? ""}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <CodeViewer
                    code={generatedPkg.supportingFiles[previewFile] ?? ""}
                    filePath={previewFile}
                  />
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {genError && (
        <div className="mx-4 mb-2 rounded-lg bg-warning/10 p-2 text-xs text-warning">
          Could not generate package — you can still start evolution with the text spec.
        </div>
      )}

      {/* Input */}
      {!finalized && (
        <div className="flex gap-2 border-t border-outline-variant p-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={sending ? "Thinking…" : "Type your reply…"}
            disabled={sending}
            className="flex-1 rounded-lg bg-surface-container-low px-3 py-2 text-sm text-on-surface placeholder:text-on-surface-dim focus:outline-none focus:ring-1 focus:ring-secondary"
          />
          <button
            onClick={submit}
            disabled={sending || !input.trim()}
            className="rounded-lg bg-secondary/20 px-4 py-2 text-xs font-medium text-secondary transition-colors hover:bg-secondary/30 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
