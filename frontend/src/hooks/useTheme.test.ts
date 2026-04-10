// @vitest-environment jsdom
//
// Tests for the useTheme cookie-backed theme hook.
//
// Carries over the testing item from PLAN-V1.1 §Testing strategy §4 that
// was specified but never landed during the v1.1 batch.
//
// Coverage:
//   - On mount: reads `skld-theme` cookie, falls back to "system" + matchMedia
//     when missing.
//   - setTheme("dark") writes the cookie and sets the resolved theme.
//   - setTheme("system") re-resolves via matchMedia.
//   - matchMedia change events flip the resolved theme when state is "system".
//   - Cookie round-trip: reloading the hook picks up the persisted value.
//
// Uses jsdom (just opted into via the docblock above — derivePhases.test.ts
// stays in the default node env, no global config change required).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";

import { useTheme } from "./useTheme";

// ---------------------------------------------------------------------------
// matchMedia + cookie helpers — install/teardown around every test so state
// doesn't leak between cases.
// ---------------------------------------------------------------------------

type MqlListener = (evt: { matches: boolean }) => void;

function installMatchMedia(initial: boolean): {
  setMatches: (v: boolean) => void;
  triggerChange: () => void;
  listenerCount: () => number;
} {
  let matches = initial;
  const listeners = new Set<MqlListener>();

  const mql = {
    get matches() {
      return matches;
    },
    media: "(prefers-color-scheme: dark)",
    addEventListener: (_event: string, cb: MqlListener) => {
      listeners.add(cb);
    },
    removeEventListener: (_event: string, cb: MqlListener) => {
      listeners.delete(cb);
    },
  };

  // jsdom doesn't ship matchMedia — stub it on window
  vi.stubGlobal("matchMedia", () => mql);

  return {
    setMatches: (v: boolean) => {
      matches = v;
    },
    triggerChange: () => {
      listeners.forEach((cb) => cb({ matches }));
    },
    listenerCount: () => listeners.size,
  };
}

function clearCookie(): void {
  // Wipe any leftover skld-theme cookie from a previous test
  document.cookie = "skld-theme=; path=/; max-age=0; samesite=lax";
}

function readRawCookie(): string | null {
  const m = document.cookie.match(/(?:^|; )skld-theme=(\w+)/);
  return m?.[1] ?? null;
}

beforeEach(() => {
  clearCookie();
  // Reset the dataset.theme between tests
  document.documentElement.removeAttribute("data-theme");
});

afterEach(() => {
  vi.unstubAllGlobals();
  clearCookie();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useTheme", () => {
  it("defaults to 'system' when no cookie is set", () => {
    installMatchMedia(false); // system prefers light
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("light");
  });

  it("resolves system → dark when prefers-color-scheme is dark", () => {
    installMatchMedia(true); // system prefers dark
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("dark");
  });

  it("reads a persisted 'dark' cookie on mount", () => {
    document.cookie = "skld-theme=dark; path=/";
    installMatchMedia(false); // shouldn't matter — explicit pref wins
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
    expect(result.current.resolved).toBe("dark");
  });

  it("reads a persisted 'light' cookie on mount", () => {
    document.cookie = "skld-theme=light; path=/";
    installMatchMedia(true); // system prefers dark, but cookie says light
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    expect(result.current.resolved).toBe("light");
  });

  it("setTheme('dark') writes the cookie + flips resolved + sets dataset.theme", () => {
    installMatchMedia(false);
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setTheme("dark");
    });

    expect(result.current.theme).toBe("dark");
    expect(result.current.resolved).toBe("dark");
    expect(readRawCookie()).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("setTheme('light') writes the cookie + flips resolved + sets dataset.theme", () => {
    installMatchMedia(true);
    const { result } = renderHook(() => useTheme());

    act(() => {
      result.current.setTheme("light");
    });

    expect(result.current.theme).toBe("light");
    expect(result.current.resolved).toBe("light");
    expect(readRawCookie()).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("setTheme('system') re-resolves via matchMedia", () => {
    document.cookie = "skld-theme=dark; path=/";
    installMatchMedia(false); // system prefers light

    const { result } = renderHook(() => useTheme());
    expect(result.current.resolved).toBe("dark");

    act(() => {
      result.current.setTheme("system");
    });

    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("light"); // re-resolved via matchMedia
    expect(readRawCookie()).toBe("system");
  });

  it("media-query change flips resolved when state is 'system'", () => {
    const mq = installMatchMedia(false); // start: prefers light
    const { result } = renderHook(() => useTheme());
    expect(result.current.resolved).toBe("light");

    // System preference flips dark — fire the listener the hook subscribed
    act(() => {
      mq.setMatches(true);
      mq.triggerChange();
    });

    expect(result.current.resolved).toBe("dark");
  });

  it("media-query listener is NOT subscribed when state is 'dark'", () => {
    document.cookie = "skld-theme=dark; path=/";
    const mq = installMatchMedia(false);
    const { result } = renderHook(() => useTheme());

    expect(result.current.theme).toBe("dark");
    // Explicit dark preference → the system listener shouldn't be active
    expect(mq.listenerCount()).toBe(0);
  });

  it("subscribes to matchMedia after setTheme('system')", () => {
    document.cookie = "skld-theme=dark; path=/";
    const mq = installMatchMedia(false);
    const { result } = renderHook(() => useTheme());
    expect(mq.listenerCount()).toBe(0);

    act(() => {
      result.current.setTheme("system");
    });

    // After flipping to system, the hook should re-subscribe
    expect(mq.listenerCount()).toBe(1);
  });

  it("cookie round-trip: a fresh render picks up the previously-set theme", () => {
    installMatchMedia(false);

    // First render: write 'dark'
    const first = renderHook(() => useTheme());
    act(() => {
      first.result.current.setTheme("dark");
    });
    expect(readRawCookie()).toBe("dark");
    first.unmount();

    // Second render: should read the cookie back
    const second = renderHook(() => useTheme());
    expect(second.result.current.theme).toBe("dark");
    expect(second.result.current.resolved).toBe("dark");
  });

  it("applies dataset.theme to <html> on mount", () => {
    document.cookie = "skld-theme=dark; path=/";
    installMatchMedia(false);
    renderHook(() => useTheme());
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
