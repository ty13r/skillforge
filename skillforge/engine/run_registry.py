"""In-process registry of active evolution runs.

Centralizes two pieces of runtime state the FastAPI process tracks for
every currently-running evolution:

- ``pending_parents`` — a ``SkillGenome`` stashed at run-start when the
  run was forked from a seed or an uploaded skill. Gen 0 spawn pops this
  to seed the initial population instead of spawning fresh.

- ``tasks`` — the backing ``asyncio.Task`` for each evolution coroutine,
  so ``DELETE /api/runs/{id}`` can cancel in-flight work.

Before this module existed, the same state lived as two mutable module
globals split across ``engine/evolution.py`` and ``api/routes.py``. That
made the state invisible to tests, impossible to reset, and fragile
under concurrent requests. A single registry with explicit accessors
replaces both. See ``docs/clean-code.md`` §5.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skillforge.models import SkillGenome


@dataclass(slots=True)
class RunRegistry:
    """Holds pending-parent and active-task state for evolution runs."""

    _pending_parents: dict[str, SkillGenome] = field(default_factory=dict)
    _tasks: dict[str, asyncio.Task] = field(default_factory=dict)

    # --- pending parents (fork-and-evolve) ---------------------------------

    def stash_parent(self, run_id: str, parent: SkillGenome) -> None:
        """Record the parent genome a run should fork from."""
        self._pending_parents[run_id] = parent

    def take_parent(self, run_id: str) -> SkillGenome | None:
        """Pop the parent genome for ``run_id`` (one-shot)."""
        return self._pending_parents.pop(run_id, None)

    # --- active evolution tasks --------------------------------------------

    def set_task(self, run_id: str, task: asyncio.Task) -> None:
        self._tasks[run_id] = task

    def clear_task(self, run_id: str) -> None:
        self._tasks.pop(run_id, None)

    def get_task(self, run_id: str) -> asyncio.Task | None:
        return self._tasks.get(run_id)

    def active_count(self) -> int:
        return len(self._tasks)

    def iter_tasks(self) -> Iterable[tuple[str, asyncio.Task]]:
        # Snapshot via list() so callers can cancel tasks without mutating
        # the dict during iteration.
        return list(self._tasks.items())


# Module-level singleton. Tests that need isolation can construct their
# own ``RunRegistry()`` and inject it explicitly; production code uses
# this shared instance.
registry = RunRegistry()
