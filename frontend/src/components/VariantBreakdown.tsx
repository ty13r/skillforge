import { useEffect, useMemo, useState } from "react";

import type { FamilyDetail, SkillFamily, Variant } from "../types";

interface VariantBreakdownProps {
  familyId: string;
}

interface SwapState {
  dimension: string;
  variantId: string;
}

/**
 * Wave 5-1 — Advanced view for atomic-mode evolution runs.
 *
 * Renders:
 *   - Foundation variants (tier=foundation) at the top with the active one
 *     highlighted and a swap dropdown listing alternatives.
 *   - Capability variants grouped by dimension below, each with a swap
 *     dropdown for alternatives in that dimension.
 *   - Re-evolve (single dimension) + Re-assemble (full family) action
 *     buttons. Wave 5-2 will wire these to the real backend endpoints.
 */
export default function VariantBreakdown({ familyId }: VariantBreakdownProps) {
  const [family, setFamily] = useState<SkillFamily | null>(null);
  const [allVariants, setAllVariants] = useState<Variant[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingSwap, setPendingSwap] = useState<SwapState | null>(null);
  const [actionStatus, setActionStatus] = useState<string | null>(null);

  // Load family detail + full variant list
  useEffect(() => {
    if (!familyId) return;
    setError(null);
    Promise.all([
      fetch(`/api/families/${familyId}`).then((r) => {
        if (!r.ok) throw new Error(`family detail HTTP ${r.status}`);
        return r.json() as Promise<FamilyDetail>;
      }),
      fetch(`/api/families/${familyId}/variants`).then((r) => {
        if (!r.ok) throw new Error(`variants HTTP ${r.status}`);
        return r.json() as Promise<Variant[]>;
      }),
    ])
      .then(([detail, variants]) => {
        setFamily(detail.family);
        setAllVariants(variants);
      })
      .catch((err) => setError(String(err)));
  }, [familyId]);

  // Group variants by (tier, dimension)
  const groups = useMemo(() => {
    const result = new Map<string, { dimension: string; tier: string; variants: Variant[] }>();
    if (!allVariants) return result;
    for (const v of allVariants) {
      const key = `${v.tier}::${v.dimension}`;
      if (!result.has(key)) {
        result.set(key, { dimension: v.dimension, tier: v.tier, variants: [] });
      }
      result.get(key)!.variants.push(v);
    }
    // Sort variants within each group by fitness DESC
    for (const group of result.values()) {
      group.variants.sort((a, b) => b.fitness_score - a.fitness_score);
    }
    return result;
  }, [allVariants]);

  const foundationGroups = useMemo(
    () => Array.from(groups.values()).filter((g) => g.tier === "foundation"),
    [groups],
  );
  const capabilityGroups = useMemo(
    () => Array.from(groups.values()).filter((g) => g.tier === "capability"),
    [groups],
  );

  async function handleSwap(dimension: string, variantId: string) {
    setPendingSwap({ dimension, variantId });
    setActionStatus(null);
    try {
      const res = await fetch(`/api/families/${familyId}/swap-variant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dimension, variant_id: variantId }),
      });
      if (!res.ok) {
        throw new Error(`swap failed: HTTP ${res.status}`);
      }
      setActionStatus(`Swapped ${dimension} → ${variantId.slice(0, 12)}`);
      // Re-fetch the variants so the active flag refreshes
      const fresh = await fetch(`/api/families/${familyId}/variants`).then((r) => r.json());
      setAllVariants(fresh);
    } catch (err) {
      setActionStatus(`Error: ${err}`);
    } finally {
      setPendingSwap(null);
    }
  }

  async function handleReEvolve(dimension: string) {
    setActionStatus(null);
    try {
      const res = await fetch(`/api/families/${familyId}/evolve-variant`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dimension }),
      });
      if (!res.ok) {
        throw new Error(`evolve failed: HTTP ${res.status}`);
      }
      const data = await res.json();
      setActionStatus(
        `Re-evolution started for ${dimension} (vevo=${data.variant_evolution_id?.slice(0, 12) ?? "?"})`,
      );
    } catch (err) {
      setActionStatus(`Error: ${err}`);
    }
  }

  if (error) {
    return (
      <div className="rounded-xl bg-error/10 p-4 text-sm text-error">
        Failed to load variant breakdown: {error}
      </div>
    );
  }

  if (!family || !allVariants) {
    return (
      <div className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-dim">
        Loading variant breakdown…
      </div>
    );
  }

  if (allVariants.length === 0) {
    return (
      <div className="rounded-xl bg-surface-container-low p-4 text-sm text-on-surface-dim">
        This family has no variants yet — atomic evolution may not have run for it. Submit a new run
        with Evolution Mode = Atomic to populate.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-outline-variant bg-surface-container-lowest p-5">
      <header className="flex items-end justify-between border-b border-outline-variant pb-3">
        <div>
          <p className="font-mono text-[0.6875rem] uppercase tracking-wider text-primary">
            Advanced — Variant Breakdown
          </p>
          <h3 className="mt-1 font-display text-xl tracking-tight">{family.label}</h3>
          <p className="mt-1 font-mono text-[0.625rem] text-on-surface-dim">
            {family.slug} · {family.decomposition_strategy}
          </p>
        </div>
        <span className="font-mono text-[0.6875rem] uppercase tracking-wider text-on-surface-dim">
          {allVariants.length} variants
        </span>
      </header>

      {actionStatus && (
        <div className="mt-3 rounded-lg bg-primary/10 p-2 font-mono text-[0.75rem] text-primary">
          {actionStatus}
        </div>
      )}

      <div className="mt-4 space-y-4">
        {foundationGroups.length > 0 && (
          <section>
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Foundation
            </p>
            <ul className="mt-2 space-y-2">
              {foundationGroups.map((g) => (
                <DimensionRow
                  key={`f-${g.dimension}`}
                  group={g}
                  pending={pendingSwap}
                  onSwap={handleSwap}
                  onReEvolve={handleReEvolve}
                />
              ))}
            </ul>
          </section>
        )}

        {capabilityGroups.length > 0 && (
          <section>
            <p className="font-mono text-[0.625rem] uppercase tracking-wider text-on-surface-dim">
              Capabilities
            </p>
            <ul className="mt-2 space-y-2">
              {capabilityGroups.map((g) => (
                <DimensionRow
                  key={`c-${g.dimension}`}
                  group={g}
                  pending={pendingSwap}
                  onSwap={handleSwap}
                  onReEvolve={handleReEvolve}
                />
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

interface DimensionRowProps {
  group: { dimension: string; tier: string; variants: Variant[] };
  pending: SwapState | null;
  onSwap: (dimension: string, variantId: string) => void;
  onReEvolve: (dimension: string) => void;
}

function DimensionRow({ group, pending, onSwap, onReEvolve }: DimensionRowProps) {
  const active = group.variants.find((v) => v.is_active) ?? group.variants[0];
  const isPending = pending !== null && pending.dimension === group.dimension;

  return (
    <li className="rounded-lg bg-surface-container-low p-3">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <code className="font-mono text-sm text-primary">{group.dimension}</code>
            <span className="font-mono text-[0.5625rem] uppercase tracking-wider text-on-surface-dim">
              {group.variants.length} variants
            </span>
          </div>
          <p className="mt-1 font-mono text-[0.625rem] text-on-surface-dim">
            active: {active?.id.slice(0, 16) ?? "—"} · fitness{" "}
            {(active?.fitness_score ?? 0).toFixed(3)}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={active?.id ?? ""}
            onChange={(e) => onSwap(group.dimension, e.target.value)}
            disabled={isPending}
            className="rounded-lg border border-outline-variant bg-surface-container-lowest px-2 py-1 font-mono text-[0.6875rem] text-on-surface"
          >
            {group.variants.map((v) => (
              <option key={v.id} value={v.id}>
                {v.id.slice(0, 12)} ({v.fitness_score.toFixed(2)})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => onReEvolve(group.dimension)}
            className="rounded-lg bg-primary/10 px-2 py-1 font-mono text-[0.625rem] uppercase tracking-wider text-primary transition-colors hover:bg-primary/20"
          >
            ⟲ Re-evolve
          </button>
        </div>
      </div>
    </li>
  );
}
