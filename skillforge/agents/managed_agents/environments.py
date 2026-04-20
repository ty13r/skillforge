"""Environment lifecycle — create / archive per-run Managed Agents environments."""

from __future__ import annotations

import contextlib

from anthropic import AsyncAnthropic

from skillforge.agents.managed_agents._constants import MANAGED_AGENTS_BETA

# ---------------------------------------------------------------------------
# Environment lifecycle
# ---------------------------------------------------------------------------


async def create_environment(
    client: AsyncAnthropic,
    *,
    run_id: str,
    packages: list[str] | None = None,
) -> str:
    """Create a cloud environment with the given pip packages pre-installed.

    Returns the environment id. The caller stores it on the EvolutionRun
    and reuses it across all competitor sessions in that run.
    """
    pkg_list = packages if packages is not None else ["pytest", "ruff"]
    resp = await client.beta.environments.create(
        name=f"sf-run-{run_id[:12]}",
        config={
            "type": "cloud",
            "packages": {
                "type": "packages",
                "pip": pkg_list,
            },
        },
        betas=[MANAGED_AGENTS_BETA],
    )
    return resp.id


async def archive_environment(client: AsyncAnthropic, environment_id: str) -> None:
    """Best-effort environment teardown. Logs and swallows errors.

    Cleanup must never block. The ``leaked_environments`` counterpart
    would go here if we needed bookkeeping; for now we accept the
    leak — environments are cheap and Anthropic GCs them.
    """
    with contextlib.suppress(Exception):
        await client.beta.environments.archive(
            environment_id,
            betas=[MANAGED_AGENTS_BETA],
        )


