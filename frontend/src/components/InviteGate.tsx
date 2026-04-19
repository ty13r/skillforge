import { useEffect, useState } from "react";

const STORAGE_KEY = "skld-invite-code";

interface InviteGateProps {
  /** Called when the user successfully validates a code. */
  onValidated: (code: string) => void;
}

/**
 * Gates /new behind invite code validation. Two modes:
 *
 *  - "I have a code" → enter + validate. On success, persists to localStorage
 *    and unlocks the page via `onValidated`.
 *  - "Request an invite" → submit email + optional message. Does NOT unlock
 *    the page; just logs the request. User must receive a code out of band
 *    (Matt reviews the invite_requests table and emails codes manually).
 *
 * Also auto-validates a code found in localStorage on mount, so returning
 * users don't see the gate at all.
 */
export default function InviteGate({ onValidated }: InviteGateProps) {
  const [tab, setTab] = useState<"code" | "request">("code");
  const [checking, setChecking] = useState(true);

  // Code-entry state
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | null>(null);
  const [submittingCode, setSubmittingCode] = useState(false);

  // Request-invite state
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);
  const [submittingRequest, setSubmittingRequest] = useState(false);
  const [requestSent, setRequestSent] = useState(false);

  // On mount: check gating status + auto-validate any stored code
  useEffect(() => {
    const run = async () => {
      try {
        const statusRes = await fetch("/api/invites/status");
        const statusData = (await statusRes.json()) as {
          gating_enabled: boolean;
        };
        if (!statusData.gating_enabled) {
          // Gating disabled — unlock immediately
          onValidated("");
          return;
        }
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const res = await fetch("/api/invites/validate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code: stored }),
          });
          if (res.ok) {
            const data = (await res.json()) as { valid: boolean };
            if (data.valid) {
              onValidated(stored);
              return;
            }
            // Stored code no longer valid — wipe it
            localStorage.removeItem(STORAGE_KEY);
          }
        }
      } catch {
        // Backend unreachable — show gate, user can try again
      }
      setChecking(false);
    };
    run();
  }, [onValidated]);

  const submitCode = async () => {
    const trimmed = code.trim();
    if (!trimmed) {
      setCodeError("Enter a code");
      return;
    }
    setSubmittingCode(true);
    setCodeError(null);
    try {
      const res = await fetch("/api/invites/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: trimmed }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { valid: boolean };
      if (data.valid) {
        localStorage.setItem(STORAGE_KEY, trimmed);
        onValidated(trimmed);
      } else {
        setCodeError("That code isn't valid. Check the spelling or request a new one.");
      }
    } catch (err) {
      setCodeError(`Error: ${String(err)}`);
    } finally {
      setSubmittingCode(false);
    }
  };

  const submitRequest = async () => {
    const trimmedEmail = email.trim();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(trimmedEmail)) {
      setRequestError("Enter a valid email address");
      return;
    }
    setSubmittingRequest(true);
    setRequestError(null);
    try {
      const res = await fetch("/api/invites/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmedEmail, message: message.trim() || null }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`HTTP ${res.status}: ${text}`);
      }
      setRequestSent(true);
    } catch (err) {
      setRequestError(String(err));
    } finally {
      setSubmittingRequest(false);
    }
  };

  if (checking) {
    return (
      <div className="mx-auto max-w-xl px-6 py-20 text-center">
        <p className="text-on-surface-dim">Checking access…</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-xl px-6 py-16">
      <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
        🔒 Invite Only
      </p>
      <h1 className="mt-2 font-display text-4xl tracking-tight">Start an Evolution Run</h1>
      <p className="mt-3 text-on-surface-dim">
        Real evolution runs consume API budget, so SKLD.run is currently invite-only. Enter your
        code below, or request an invite and we'll email you one.
      </p>

      {/* Tabs */}
      <div className="mt-8 flex gap-1 rounded-xl border border-outline-variant bg-surface-container-low p-1">
        <button
          onClick={() => setTab("code")}
          className={`flex-1 rounded-lg px-3 py-2 font-mono text-[0.6875rem] uppercase tracking-wider transition-colors ${
            tab === "code"
              ? "bg-primary/15 text-primary"
              : "text-on-surface-dim hover:text-on-surface"
          }`}
        >
          I have a code
        </button>
        <button
          onClick={() => setTab("request")}
          className={`flex-1 rounded-lg px-3 py-2 font-mono text-[0.6875rem] uppercase tracking-wider transition-colors ${
            tab === "request"
              ? "bg-primary/15 text-primary"
              : "text-on-surface-dim hover:text-on-surface"
          }`}
        >
          Request an invite
        </button>
      </div>

      {tab === "code" && (
        <div className="mt-6 space-y-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          <div>
            <label className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
              Invite Code
            </label>
            <input
              type="text"
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setCodeError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitCode();
              }}
              placeholder="e.g. ALPHA-M7F2"
              autoFocus
              className="mt-2 w-full rounded-lg border border-outline-variant bg-surface-container-low px-4 py-2.5 font-mono text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
            />
            {codeError && <p className="mt-2 text-xs text-error">{codeError}</p>}
          </div>
          <button
            onClick={submitCode}
            disabled={submittingCode}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-surface-container-lowest transition-colors hover:bg-primary/90 disabled:opacity-60"
          >
            {submittingCode ? "Validating…" : "Unlock →"}
          </button>
        </div>
      )}

      {tab === "request" && (
        <div className="mt-6 space-y-4 rounded-xl border border-outline-variant bg-surface-container-lowest p-6">
          {requestSent ? (
            <>
              <p className="font-display text-xl tracking-tight text-tertiary">
                ✓ Request received
              </p>
              <p className="text-sm text-on-surface-dim">
                Thanks — your request has been logged. We review new invites regularly and will
                email you a code if we can onboard you. This does <strong>not</strong> unlock the
                platform; you'll need to enter the code when it arrives.
              </p>
              <button
                onClick={() => {
                  setRequestSent(false);
                  setEmail("");
                  setMessage("");
                  setTab("code");
                }}
                className="hover:bg-surface-container-mid w-full rounded-lg border border-outline-variant bg-surface-container-low px-4 py-2.5 text-sm text-on-surface transition-colors"
              >
                I already have a code →
              </button>
            </>
          ) : (
            <>
              <div>
                <label className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setRequestError(null);
                  }}
                  placeholder="you@example.com"
                  className="mt-2 w-full rounded-lg border border-outline-variant bg-surface-container-low px-4 py-2.5 text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
                />
              </div>
              <div>
                <label className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
                  What would you use it for? (optional)
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={3}
                  placeholder="Tell us about the Skill you want to evolve…"
                  maxLength={1000}
                  className="mt-2 w-full rounded-lg border border-outline-variant bg-surface-container-low px-4 py-2.5 text-sm text-on-surface placeholder:text-on-surface-dim/60 focus:border-primary focus:outline-none"
                />
              </div>
              {requestError && <p className="text-xs text-error">{requestError}</p>}
              <p className="text-[0.6875rem] text-on-surface-dim">
                Submitting does not automatically grant access. We'll review and email a code if we
                can onboard you.
              </p>
              <button
                onClick={submitRequest}
                disabled={submittingRequest}
                className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-surface-container-lowest transition-colors hover:bg-primary/90 disabled:opacity-60"
              >
                {submittingRequest ? "Submitting…" : "Request invite"}
              </button>
            </>
          )}
        </div>
      )}

      <p className="mt-6 text-center text-xs text-on-surface-dim">
        Want to see the platform in action first?{" "}
        <a href="/runs/demo-live" className="text-primary underline">
          Watch the live demo
        </a>{" "}
        — no code required.
      </p>
    </div>
  );
}
