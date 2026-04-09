import { useEffect, useRef, useState } from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface SpecAssistantChatProps {
  onSpecReady: (spec: string) => void;
}

export default function SpecAssistantChat({ onSpecReady }: SpecAssistantChatProps) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finalized, setFinalized] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

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
      // Fire the seed turn (empty history → backend sends greeting)
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
  };

  if (!open) {
    return (
      <button
        onClick={open_}
        className="mt-2 inline-flex items-center gap-2 rounded-lg border border-secondary/30 bg-secondary/5 px-3 py-1.5 text-xs text-secondary transition-colors hover:bg-secondary/10"
      >
        ✨ Help me write this with AI
      </button>
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
          {finalized && (
            <span className="rounded-full bg-tertiary/15 px-2 py-0.5 font-mono text-[0.625rem] uppercase tracking-wider text-tertiary">
              ✓ filled
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
