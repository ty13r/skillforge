import { useEffect, useState } from "react";

/**
 * Read a CSS custom property off `<html>` and return it as an `rgb(...)` string
 * that third-party libraries like Recharts can consume directly. Re-runs when
 * `document.documentElement.dataset.theme` changes so charts re-theme on toggle.
 *
 * Usage: `const primary = useCssVar("--color-primary");`  →  `"rgb(217 119 87)"`
 */
export function useCssVar(name: string, alpha = 1): string {
  const [value, setValue] = useState<string>("");

  useEffect(() => {
    const read = () => {
      const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      if (!raw) {
        setValue("");
        return;
      }
      setValue(alpha < 1 ? `rgb(${raw} / ${alpha})` : `rgb(${raw})`);
    };
    read();

    // Observe theme attribute changes on <html>
    const obs = new MutationObserver(read);
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    // Also react to prefers-color-scheme changes in case theme is "system"
    const mq = matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", read);

    return () => {
      obs.disconnect();
      mq.removeEventListener("change", read);
    };
  }, [name, alpha]);

  return value;
}
