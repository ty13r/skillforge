import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

const COOKIE_NAME = "skld-theme";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // 1 year

function readCookie(): Theme {
  const m = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_NAME}=(\\w+)`));
  const v = m?.[1];
  if (v === "light" || v === "dark" || v === "system") return v;
  return "system";
}

function writeCookie(theme: Theme): void {
  document.cookie = `${COOKIE_NAME}=${theme}; path=/; max-age=${COOKIE_MAX_AGE}; samesite=lax`;
}

function systemPrefers(): ResolvedTheme {
  if (typeof window === "undefined") return "light";
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function resolve(theme: Theme): ResolvedTheme {
  return theme === "system" ? systemPrefers() : theme;
}

/**
 * Cookie-backed theme state. Tracks a 3-state user preference
 * (light | dark | system) and exposes both the raw preference and the
 * resolved concrete value. Writes `document.documentElement.dataset.theme`
 * on every change so Tailwind's CSS-variable palette swap kicks in.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() =>
    typeof window === "undefined" ? "system" : readCookie(),
  );
  const [resolved, setResolved] = useState<ResolvedTheme>(() =>
    typeof window === "undefined" ? "light" : resolve(readCookie()),
  );

  // Apply the resolved theme to <html> whenever it changes
  useEffect(() => {
    document.documentElement.dataset.theme = resolved;
  }, [resolved]);

  // Listen for system preference changes when theme === "system"
  useEffect(() => {
    if (theme !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const handler = () => setResolved(systemPrefers());
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const setTheme = useCallback((next: Theme) => {
    writeCookie(next);
    setThemeState(next);
    setResolved(resolve(next));
  }, []);

  return { theme, resolved, setTheme };
}
