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

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dict."""
        return {
            "skill_id": self.skill_id,
            "challenge_id": self.challenge_id,
            "output_files": self.output_files,
            "trace": self.trace,
            "compiles": self.compiles,
            "tests_pass": self.tests_pass,
            "lint_score": self.lint_score,
            "perf_metrics": self.perf_metrics,
            "trigger_precision": self.trigger_precision,
            "trigger_recall": self.trigger_recall,
            "skill_was_loaded": self.skill_was_loaded,
            "instructions_followed": self.instructions_followed,
            "instructions_ignored": self.instructions_ignored,
            "ignored_diagnostics": self.ignored_diagnostics,
            "scripts_executed": self.scripts_executed,
            "behavioral_signature": self.behavioral_signature,
            "pairwise_wins": self.pairwise_wins,
            "pareto_objectives": self.pareto_objectives,
            "trait_contribution": self.trait_contribution,
            "trait_diagnostics": self.trait_diagnostics,
            "judge_reasoning": self.judge_reasoning,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CompetitionResult:
        """Rehydrate from a dict."""
        return cls(
            skill_id=data["skill_id"],
            challenge_id=data["challenge_id"],
            output_files=data.get("output_files", {}),
            trace=data.get("trace", []),
            compiles=data.get("compiles", False),
            tests_pass=data.get("tests_pass"),
            lint_score=data.get("lint_score"),
            perf_metrics=data.get("perf_metrics", {}),
            trigger_precision=data.get("trigger_precision", 0.0),
            trigger_recall=data.get("trigger_recall", 0.0),
            skill_was_loaded=data.get("skill_was_loaded", False),
            instructions_followed=data.get("instructions_followed", []),
            instructions_ignored=data.get("instructions_ignored", []),
            ignored_diagnostics=data.get("ignored_diagnostics", {}),
            scripts_executed=data.get("scripts_executed", []),
            behavioral_signature=data.get("behavioral_signature", []),
            pairwise_wins=data.get("pairwise_wins", {}),
            pareto_objectives=data.get("pareto_objectives", {}),
            trait_contribution=data.get("trait_contribution", {}),
            trait_diagnostics=data.get("trait_diagnostics", {}),
            judge_reasoning=data.get("judge_reasoning", ""),
        )
