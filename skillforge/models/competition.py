"""CompetitionResult — the outcome of one Skill running one Challenge.

Carries the full execution trace and per-layer fitness fields populated by
the 6-layer judging pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompetitionResult:
    """Result of a single Skill × Challenge competition."""

    skill_id: str
    challenge_id: str
    output_files: dict[str, str] = field(default_factory=dict)
    trace: list[dict] = field(default_factory=list)

    # L1: Deterministic
    compiles: bool = False
    tests_pass: bool | None = None
    lint_score: float | None = None
    perf_metrics: dict[str, float] = field(default_factory=dict)

    # L2: Trigger accuracy
    trigger_precision: float = 0.0
    trigger_recall: float = 0.0

    # L3: Trace-based behavioral analysis
    skill_was_loaded: bool = False
    instructions_followed: list[str] = field(default_factory=list)
    instructions_ignored: list[str] = field(default_factory=list)
    ignored_diagnostics: dict[str, str] = field(default_factory=dict)
    scripts_executed: list[str] = field(default_factory=list)
    behavioral_signature: list[str] = field(default_factory=list)

    # L4: Comparative + Pareto
    pairwise_wins: dict[str, int] = field(default_factory=dict)
    pareto_objectives: dict[str, float] = field(default_factory=dict)

    # L5: Trait attribution
    trait_contribution: dict[str, float] = field(default_factory=dict)
    trait_diagnostics: dict[str, str] = field(default_factory=dict)
    judge_reasoning: str = ""
