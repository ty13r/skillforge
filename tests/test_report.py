"""Wave 1-5 tests — post-run report generator.

Covers:
- ``generate_run_report`` assembles every required section from a fully
  persisted EvolutionRun (mock data, no LLM calls).
- All required top-level keys present.
- ``metadata.duration_sec`` computed correctly from created_at → completed_at.
- ``summary.best_skill_id`` reflects the run's best skill.
- JSON payload stays under 1MB even with multiple generations.
- Markdown sidecar renders all key sections.
- ``generate_run_report`` is a no-op when the run does not exist.
- ``get_report`` round-trips via disk.
- The 404 API endpoint path.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from skillforge.db import init_db, save_run
from skillforge.engine.report import (
    MAX_REPORT_BYTES,
    SKILL_MD_PREVIEW_LINES,
    generate_run_report,
    get_report,
)
from skillforge.main import app
from skillforge.models import (
    Challenge,
    CompetitionResult,
    EvolutionRun,
    Generation,
    SkillGenome,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Factories — hand-built so every field the report touches is populated
# ---------------------------------------------------------------------------


def _make_genome(
    gid: str = "s1",
    generation: int = 0,
    traits: list[str] | None = None,
    content: str = "# Test skill\n",
) -> SkillGenome:
    return SkillGenome(
        id=gid,
        generation=generation,
        skill_md_content=content,
        frontmatter={"name": "test"},
        supporting_files={},
        traits=traits or ["fast", "accurate"],
        meta_strategy="greedy",
        parent_ids=[],
        mutations=[],
        mutation_rationale="",
        maturity="tested",
        generations_survived=1,
        deterministic_scores={"compile": 1.0},
        trigger_precision=0.9,
        trigger_recall=0.85,
        behavioral_signature=["load", "run"],
        pareto_objectives={"quality": 0.9, "speed": 0.7},
        is_pareto_optimal=True,
        trait_attribution={"fast": 0.6, "accurate": 0.4},
        trait_diagnostics={"fast": "caches"},
    )


def _make_challenge(cid: str = "c1") -> Challenge:
    return Challenge(
        id=cid,
        prompt="reverse a string",
        difficulty="easy",
        evaluation_criteria={"correctness": 1.0},
        verification_method="run_tests",
        setup_files={},
        gold_standard_hints="s[::-1]",
    )


def _make_competition_result(
    skill_id: str, challenge_id: str, _run_id: str = ""
) -> CompetitionResult:
    """run_id is unused — CompetitionResult stores it via FK on the DB row
    when persisted, but the dataclass itself doesn't have a run_id field."""
    return CompetitionResult(
        skill_id=skill_id,
        challenge_id=challenge_id,
        output_files={"solution.py": "print('ok')"},
        trace=[],
        compiles=True,
        tests_pass=True,
        lint_score=0.9,
        perf_metrics={},
        trigger_precision=0.9,
        trigger_recall=0.85,
        skill_was_loaded=True,
        instructions_followed=["load_skill"],
        instructions_ignored=[],
        ignored_diagnostics={},
        scripts_executed=["solution.py"],
        behavioral_signature=["load", "run"],
        pairwise_wins={},
        pareto_objectives={"quality": 0.9},
        trait_contribution={"fast": 0.6},
        trait_diagnostics={"fast": "cached"},
        judge_reasoning="solid baseline",
    )


def _make_full_run(run_id: str = "run_test_1") -> EvolutionRun:
    # Unique skill + challenge ids per run so save_genome's ON CONFLICT
    # upsert (which preserves run_id) doesn't leak state across tests.
    unique = uuid.uuid4().hex[:8]
    skill = _make_genome(gid=f"s_{unique}")
    challenge = _make_challenge(cid=f"c_{unique}")
    generation = Generation(
        number=0,
        skills=[skill],
        results=[
            _make_competition_result(skill.id, challenge.id, run_id),
        ],
        best_fitness=0.85,
        avg_fitness=0.80,
        pareto_front=[skill.id],
        breeding_report="",
        learning_log_entries=["first lesson"],
        trait_survival={"fast": True, "accurate": True},
        trait_emergence=[],
    )
    return EvolutionRun(
        id=run_id,
        mode="domain",
        specialization="reverse strings",
        population_size=2,
        num_generations=1,
        challenges=[challenge],
        generations=[generation],
        learning_log=["first lesson", "second lesson"],
        status="complete",
        created_at=datetime(2026, 4, 10, 12, 0, tzinfo=UTC),
        completed_at=datetime(2026, 4, 10, 12, 5, tzinfo=UTC),
        best_skill=skill,
        pareto_front=[skill],
        total_cost_usd=0.42,
        max_budget_usd=10.0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_generate_run_report_assembles_all_sections(tmp_path: Path):
    await init_db()
    run = _make_full_run(f"run_{uuid.uuid4().hex[:8]}")
    await save_run(run)

    report = await generate_run_report(run.id, reports_dir=tmp_path)
    assert report is not None

    # Required top-level keys
    expected_keys = {
        "metadata",
        "taxonomy",
        "challenges",
        "generations",
        "variant_evolutions",
        "assembly_report",
        "bible_findings",
        "learning_log",
        "summary",
        "generated_at",
    }
    assert expected_keys.issubset(report.keys())

    # Metadata sanity checks
    meta = report["metadata"]
    assert meta["run_id"] == run.id
    assert meta["specialization"] == "reverse strings"
    assert meta["status"] == "complete"
    assert meta["evolution_mode"] == "molecular"  # default for pre-v2.0 runs
    assert meta["duration_sec"] == pytest.approx(300.0)  # 5 minutes

    # Summary
    summary = report["summary"]
    assert summary["best_skill_id"] == run.best_skill.id
    assert summary["aggregate_fitness"] == pytest.approx(0.85)
    assert summary["total_cost_usd"] == pytest.approx(0.42)
    assert summary["key_discoveries"]  # at least one lesson

    # Challenges mirror the run's challenge list
    assert len(report["challenges"]) == 1
    assert report["challenges"][0]["prompt"] == "reverse a string"

    # Generations section has the fitness curve
    assert len(report["generations"]) == 1
    gen = report["generations"][0]
    assert gen["fitness_curve"]["best"] == pytest.approx(0.85)
    assert gen["fitness_curve"]["avg"] == pytest.approx(0.80)
    assert gen["fitness_curve"]["delta_from_prev"] is None
    assert len(gen["skills"]) == 1

    # The skill entry should include the preview + fitness breakdown
    skill_entry = gen["skills"][0]
    assert "fitness_breakdown" in skill_entry
    assert skill_entry["is_pareto_optimal"] is True
    assert skill_entry["skill_md_preview"].startswith("# Test skill")

    # Variant evolutions + assembly are empty for molecular runs
    assert report["variant_evolutions"] == []
    assert report["assembly_report"] is None  # no family_id


async def test_report_files_written_to_disk(tmp_path: Path):
    await init_db()
    run = _make_full_run(f"run_{uuid.uuid4().hex[:8]}")
    await save_run(run)

    await generate_run_report(run.id, reports_dir=tmp_path)

    json_path = tmp_path / f"{run.id}.json"
    md_path = tmp_path / f"{run.id}.md"
    assert json_path.exists()
    assert md_path.exists()

    # JSON reloads cleanly
    payload = json.loads(json_path.read_text())
    assert payload["metadata"]["run_id"] == run.id

    # Markdown has the expected headers
    md = md_path.read_text()
    assert "# Run Report —" in md
    assert "## Summary" in md
    assert "## Generations" in md


async def test_report_size_stays_under_cap(tmp_path: Path):
    """Even with a few generations + long skill content, report should
    stay well under MAX_REPORT_BYTES thanks to the preview truncation."""
    await init_db()
    run = _make_full_run(f"run_{uuid.uuid4().hex[:8]}")

    # Inflate the skill md content with 500 lines — the preview cap should
    # still keep the serialized report small.
    big_content = "\n".join(f"line {i}: " + "x" * 100 for i in range(500))
    for gen in run.generations:
        for skill in gen.skills:
            skill.skill_md_content = big_content

    await save_run(run)

    report = await generate_run_report(run.id, reports_dir=tmp_path)
    assert report is not None

    payload = json.dumps(report, indent=2, default=str)
    assert len(payload.encode("utf-8")) < MAX_REPORT_BYTES

    # Preview in report should be truncated
    gen_entry = report["generations"][0]
    skill_entry = gen_entry["skills"][0]
    preview_lines = skill_entry["skill_md_preview"].splitlines()
    # Preview contains first N lines + one "... (truncated)" marker
    assert len(preview_lines) <= SKILL_MD_PREVIEW_LINES + 1
    assert preview_lines[-1] == "... (truncated)"


async def test_generate_run_report_returns_none_for_missing(tmp_path: Path):
    await init_db()
    result = await generate_run_report("nope-not-a-real-id", reports_dir=tmp_path)
    assert result is None


async def test_get_report_roundtrip_via_disk(tmp_path: Path):
    await init_db()
    run = _make_full_run(f"run_{uuid.uuid4().hex[:8]}")
    await save_run(run)

    generated = await generate_run_report(run.id, reports_dir=tmp_path)
    assert generated is not None

    loaded = await get_report(run.id, reports_dir=tmp_path)
    assert loaded is not None
    assert loaded["metadata"]["run_id"] == run.id
    assert loaded["summary"]["best_skill_id"] == run.best_skill.id


async def test_get_report_returns_none_when_missing(tmp_path: Path):
    result = await get_report("nope-not-a-real-id", reports_dir=tmp_path)
    assert result is None


async def test_report_fitness_delta_across_generations(tmp_path: Path):
    """When there are 2+ generations, delta_from_prev should compute."""
    await init_db()
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    skill0 = _make_genome(gid=f"s0_{run_id}", generation=0)
    skill1 = _make_genome(gid=f"s1_{run_id}", generation=1)

    challenge = _make_challenge(f"c_{run_id}")

    gen0 = Generation(
        number=0,
        skills=[skill0],
        results=[_make_competition_result(skill0.id, challenge.id, run_id)],
        best_fitness=0.6,
        avg_fitness=0.55,
        pareto_front=[skill0.id],
        breeding_report="",
        learning_log_entries=[],
        trait_survival={},
        trait_emergence=[],
    )
    gen1 = Generation(
        number=1,
        skills=[skill1],
        results=[_make_competition_result(skill1.id, challenge.id, run_id)],
        best_fitness=0.82,
        avg_fitness=0.70,
        pareto_front=[skill1.id],
        breeding_report="",
        learning_log_entries=[],
        trait_survival={},
        trait_emergence=[],
    )

    run = EvolutionRun(
        id=run_id,
        mode="domain",
        specialization="x",
        population_size=2,
        num_generations=2,
        challenges=[challenge],
        generations=[gen0, gen1],
        status="complete",
        created_at=datetime.now(UTC) - timedelta(minutes=10),
        completed_at=datetime.now(UTC),
        best_skill=skill1,
        total_cost_usd=1.0,
        max_budget_usd=10.0,
    )
    await save_run(run)

    report = await generate_run_report(run.id, reports_dir=tmp_path)
    assert report is not None

    gens = report["generations"]
    assert len(gens) == 2
    assert gens[0]["fitness_curve"]["delta_from_prev"] is None
    assert gens[1]["fitness_curve"]["delta_from_prev"] == pytest.approx(0.22)


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("run_id", ["run-that-does-not-exist"])
async def test_get_report_endpoint_404_when_missing(run_id: str):
    client = TestClient(app)
    resp = client.get(f"/api/runs/{run_id}/report")
    assert resp.status_code == 404
    assert "not generated" in resp.json()["detail"]
