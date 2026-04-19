"""Agent tests: Challenge Designer, Spawner, Competitor, Breeder (Step 6).

Challenge Designer and Spawner use the Anthropic Messages API directly
(NOT the Agent SDK's query()). Tests mock the internal ``_generate`` helper
which takes a prompt string and returns a text string — a much simpler
seam than mocking the API client.
"""

from unittest.mock import patch

import pytest

from skillforge.agents.challenge_designer import design_challenges
from skillforge.agents.spawner import breed_next_gen, spawn_gen0
from skillforge.engine.sandbox import validate_skill_structure
from skillforge.models import Challenge, SkillGenome

# ---------------------------------------------------------------------------
# Mock helpers — the new seam is just "prompt in, text out"
# ---------------------------------------------------------------------------


def _make_generate_mock(responses: list[str]):
    """Return an async side_effect function that yields ``responses`` in order.

    After all responses are consumed, subsequent calls return the last
    response (defensive — avoids IndexError if the code accidentally
    calls one more time than expected).
    """
    idx = {"i": 0}

    async def fake_generate(prompt: str) -> str:
        i = min(idx["i"], len(responses) - 1)
        idx["i"] += 1
        return responses[i]

    return fake_generate


# A reusable valid payload of 3 challenges
_THREE_CHALLENGES_JSON = """[
  {
    "prompt": "Write a GenServer rate limiter.",
    "difficulty": "medium",
    "evaluation_criteria": {"correctness": 0.5, "idiomaticity": 0.5},
    "verification_method": "run_tests",
    "setup_files": {"test_rate_limiter.ex": "# tests"},
    "gold_standard_hints": "use sliding window"
  },
  {
    "prompt": "Build a supervisor tree for a fault-tolerant worker pool.",
    "difficulty": "hard",
    "evaluation_criteria": {"correctness": 0.6, "robustness": 0.4},
    "verification_method": "judge_review",
    "setup_files": {},
    "gold_standard_hints": "one_for_one strategy with transient children"
  },
  {
    "prompt": "Create a Phoenix LiveView counter.",
    "difficulty": "easy",
    "evaluation_criteria": {"correctness": 1.0},
    "verification_method": "run_tests",
    "setup_files": {"test_counter.exs": "# tests"},
    "gold_standard_hints": "use handle_event with :inc"
  }
]"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_design_challenges_returns_n_challenges():
    """Happy path: fenced JSON block → 3 challenges."""
    fake_text = f"Here are the challenges:\n```json\n{_THREE_CHALLENGES_JSON}\n```"

    with patch(
        "skillforge.agents.challenge_designer._generate",
        side_effect=_make_generate_mock([fake_text]),
    ):
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    assert len(challenges) == 3
    assert all(isinstance(c, Challenge) for c in challenges)
    assert {c.difficulty for c in challenges} == {"easy", "medium", "hard"}
    assert all(c.id for c in challenges)


async def test_design_challenges_accepts_bare_json_array():
    """No ```json fence — just a bare JSON array in the response."""
    with patch(
        "skillforge.agents.challenge_designer._generate",
        side_effect=_make_generate_mock([_THREE_CHALLENGES_JSON.strip()]),
    ):
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    assert len(challenges) == 3
    assert all(isinstance(c, Challenge) for c in challenges)


async def test_design_challenges_retries_on_parse_failure():
    """First response is garbage; second is valid. _generate called twice."""
    good_text = f"```json\n{_THREE_CHALLENGES_JSON}\n```"

    call_count = {"n": 0}

    async def fake(prompt: str) -> str:
        call_count["n"] += 1
        return "This is not JSON at all!" if call_count["n"] == 1 else good_text

    with patch("skillforge.agents.challenge_designer._generate", side_effect=fake):
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    assert call_count["n"] == 2
    assert len(challenges) == 3


async def test_design_challenges_raises_on_repeated_parse_failure():
    """Both attempts return garbage → ValueError."""
    with patch(
        "skillforge.agents.challenge_designer._generate",
        side_effect=_make_generate_mock(["not json at all", "still not json"]),
    ), pytest.raises(ValueError, match="2 attempts"):
        await design_challenges("Elixir LiveView specialist", n=3)


async def test_design_challenges_raises_if_count_mismatch():
    """Claude returns 2 challenges but n=3 → ValueError."""
    two_challenges_json = """[
      {
        "prompt": "Write a GenServer.",
        "difficulty": "easy",
        "evaluation_criteria": {"correctness": 1.0},
        "verification_method": "run_tests",
        "setup_files": {},
        "gold_standard_hints": "keep it simple"
      },
      {
        "prompt": "Build a supervisor.",
        "difficulty": "medium",
        "evaluation_criteria": {"correctness": 0.7, "robustness": 0.3},
        "verification_method": "judge_review",
        "setup_files": {},
        "gold_standard_hints": "one_for_one"
      }
    ]"""
    fake_text = f"```json\n{two_challenges_json}\n```"

    with patch(
        "skillforge.agents.challenge_designer._generate",
        side_effect=_make_generate_mock([fake_text]),
    ), pytest.raises(ValueError, match="expected 3"):
        await design_challenges("Elixir LiveView specialist", n=3)


async def test_design_challenges_generates_unique_ids():
    """All returned Challenges have distinct UUIDs."""
    fake_text = f"```json\n{_THREE_CHALLENGES_JSON}\n```"

    with patch(
        "skillforge.agents.challenge_designer._generate",
        side_effect=_make_generate_mock([fake_text]),
    ):
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    ids = [c.id for c in challenges]
    assert len(ids) == len(set(ids))


# ===========================================================================
# Spawner helpers
# ===========================================================================


def _valid_skill_json(name: str = "my-skill") -> dict:
    """Return a minimal-but-valid skill JSON dict as Claude would produce."""
    skill_md = (
        f"---\n"
        f"name: {name}\n"
        f"description: >-\n"
        f"  Helps you with {name} tasks. Use when you need {name} assistance,\n"
        f'  or when user mentions "{name}", even if they don\'t explicitly ask for {name}.\n'
        f"  NOT for unrelated domains.\n"
        f"allowed-tools: Read Write Bash\n"
        f"---\n"
        f"\n"
        f"# {name.replace('-', ' ').title()}\n"
        f"\n"
        f"## Quick Start\n"
        f"Run the skill to produce output for {name}.\n"
        f"\n"
        f"## Workflow\n"
        f"\n"
        f"### Step 1: Gather Context\n"
        f"Read the user request carefully.\n"
        f"\n"
        f"### Step 2: Execute\n"
        f"Perform the {name} task.\n"
        f"\n"
        f"### Step 3: Validate\n"
        f"Check output meets quality bar.\n"
        f"\n"
        f"## Examples\n"
        f"\n"
        f"**Example 1: Typical use case**\n"
        f'Input: "Do {name} thing"\n'
        f"Output: Correct {name} result\n"
        f"\n"
        f"**Example 2: Edge case**\n"
        f'Input: "Handle edge case for {name}"\n'
        f"Output: Edge case handled correctly\n"
        f"\n"
        f"## Gotchas\n"
        f"- Watch for {name} specific edge cases.\n"
        f"\n"
        f"## Out of Scope\n"
        f"This skill does NOT:\n"
        f"- Handle unrelated domain tasks.\n"
    )
    return {
        "name": name,
        "skill_md_content": skill_md,
        "supporting_files": {},
        "traits": ["imperative-phrasing"],
        "meta_strategy": "plan-first",
    }


def _valid_skill_json_with_parent(name: str, parent_ids: list[str]) -> dict:
    """Valid skill JSON with parent_ids and mutation fields."""
    base = _valid_skill_json(name)
    base["parent_ids"] = parent_ids
    base["mutations"] = ["changed-meta-strategy"]
    base["mutation_rationale"] = "Parent attribution showed plan-first works better."
    return base


def _make_parent_genome(name: str = "parent-skill", generation: int = 0) -> SkillGenome:
    """Build a minimal valid parent SkillGenome for breeding tests."""
    data = _valid_skill_json(name)
    return SkillGenome(
        id=str(__import__("uuid").uuid4()),
        generation=generation,
        skill_md_content=data["skill_md_content"],
        supporting_files=data["supporting_files"],
        traits=data["traits"],
        meta_strategy=data["meta_strategy"],
    )


# ===========================================================================
# Spawner tests — spawn_gen0
# ===========================================================================


async def test_spawn_gen0_returns_valid_population():
    """Happy path: mock _generate returns 3 valid skills → 3 SkillGenome objects."""
    import json as _json

    skills = [_valid_skill_json(f"skill-{i}") for i in range(3)]
    fake_text = _json.dumps(skills)

    with patch(
        "skillforge.agents.spawner._generate",
        side_effect=_make_generate_mock([fake_text]),
    ):
        population = await spawn_gen0("Elixir specialist", pop_size=3)

    assert len(population) == 3
    assert all(isinstance(g, SkillGenome) for g in population)
    assert all(g.generation == 0 for g in population)
    for genome in population:
        violations = validate_skill_structure(genome)
        assert violations == [], f"Genome {genome.id} has violations: {violations}"
    ids = [g.id for g in population]
    assert len(ids) == len(set(ids))


async def test_spawn_gen0_reads_bible_patterns():
    """System prompt must include bible pattern content."""
    import json as _json

    skills = [_valid_skill_json("my-skill")]
    fake_text = _json.dumps(skills)
    captured_prompts: list[str] = []

    async def capturing_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return fake_text

    with patch(
        "skillforge.agents.spawner._read_bible_patterns",
        return_value="PATTERN_MARKER_ABC",
    ), patch(
        "skillforge.agents.spawner._generate",
        side_effect=capturing_generate,
    ):
        await spawn_gen0("test domain", pop_size=1)

    assert captured_prompts, "_generate should have been called"
    assert "PATTERN_MARKER_ABC" in captured_prompts[0]


async def test_spawn_gen0_handles_missing_bible_dir(tmp_path, monkeypatch):
    """spawn_gen0 works even if BIBLE_DIR doesn't exist."""
    import json as _json

    import skillforge.agents.spawner as spawner_mod

    monkeypatch.setattr(spawner_mod, "BIBLE_DIR", tmp_path / "nonexistent-bible-dir")
    assert spawner_mod._read_bible_patterns() == ""

    skills = [_valid_skill_json("my-skill")]
    fake_text = _json.dumps(skills)

    with patch(
        "skillforge.agents.spawner._generate",
        side_effect=_make_generate_mock([fake_text]),
    ):
        population = await spawn_gen0("test domain", pop_size=1)

    assert len(population) == 1
    assert population[0].generation == 0


async def test_spawn_gen0_retries_on_invalid_skill():
    """First response has 1 invalid skill; second response fixes all."""
    import json as _json

    valid_skill = _valid_skill_json("good-skill")
    invalid_skill = {
        "name": "bad-skill",
        "skill_md_content": "# No frontmatter — this will fail validation",
        "supporting_files": {},
        "traits": [],
        "meta_strategy": "",
    }
    retry_skills = [_valid_skill_json("fixed-skill-1"), _valid_skill_json("fixed-skill-2")]

    call_count = {"n": 0}

    async def fake(prompt: str) -> str:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _json.dumps([valid_skill, invalid_skill])
        return _json.dumps(retry_skills)

    with patch("skillforge.agents.spawner._generate", side_effect=fake):
        population = await spawn_gen0("test domain", pop_size=2)

    assert call_count["n"] == 2
    assert len(population) >= 1
    for genome in population:
        assert validate_skill_structure(genome) == []


async def test_spawn_gen0_raises_on_persistent_invalid():
    """Both attempts return invalid skills → ValueError with violations."""
    import json as _json

    bad_skill = {
        "name": "bad-skill",
        "skill_md_content": "# No frontmatter — always invalid",
        "supporting_files": {},
        "traits": [],
        "meta_strategy": "",
    }
    bad_text = _json.dumps([bad_skill])

    with patch(
        "skillforge.agents.spawner._generate",
        side_effect=_make_generate_mock([bad_text, bad_text]),
    ), pytest.raises(ValueError, match="invalid skills after retry"):
        await spawn_gen0("test domain", pop_size=1)


def test_auto_repair_missing_references_stubs_missing_files():
    """Rule-8 drift: a body references a file that isn't in supporting_files.

    The repair pass stubs it with a placeholder so the genome passes
    structural validation instead of killing the whole population on a
    cosmetic miss.
    """
    from skillforge.agents.spawner import _auto_repair_missing_references

    skill_md = (
        "---\nname: x\ndescription: Use when y.\n---\n\n"
        "# X\n\nSee ${CLAUDE_SKILL_DIR}/references/style-guide.md for details.\n"
    )
    genome = SkillGenome(
        id="g1",
        generation=0,
        skill_md_content=skill_md,
        supporting_files={},
        traits=[],
    )
    stubbed = _auto_repair_missing_references(genome)
    assert stubbed == 1
    assert "references/style-guide.md" in genome.supporting_files
    assert genome.supporting_files["references/style-guide.md"].startswith(
        "# Style Guide"
    )


def test_auto_repair_missing_references_noop_when_all_present():
    """If every reference already resolves, the repair must not touch anything."""
    from skillforge.agents.spawner import _auto_repair_missing_references

    skill_md = (
        "---\nname: x\ndescription: Use when y.\n---\n\n"
        "# X\n\nSee ${CLAUDE_SKILL_DIR}/references/guide.md.\n"
    )
    genome = SkillGenome(
        id="g2",
        generation=0,
        skill_md_content=skill_md,
        supporting_files={"references/guide.md": "# real content"},
        traits=[],
    )
    stubbed = _auto_repair_missing_references(genome)
    assert stubbed == 0
    assert genome.supporting_files["references/guide.md"] == "# real content"


# ===========================================================================
# Spawner tests — breed_next_gen
# ===========================================================================


async def test_breed_next_gen_sets_parent_ids_and_generation():
    """Children must have generation=1 and parent_ids matching the parents."""
    import json as _json

    parent1 = _make_parent_genome("parent-one", generation=0)
    parent2 = _make_parent_genome("parent-two", generation=0)

    child1 = _valid_skill_json_with_parent("child-one", [parent1.id, parent2.id])
    child2 = _valid_skill_json_with_parent("child-two", [parent1.id, parent2.id])
    fake_text = _json.dumps([child1, child2])

    with patch(
        "skillforge.agents.spawner._generate",
        side_effect=_make_generate_mock([fake_text]),
    ):
        children = await breed_next_gen(
            parents=[parent1, parent2],
            learning_log=["gen0: plan-first strategy outperformed dive-in"],
            breeding_instructions="Breed 2 children mixing the parents' strategies.",
        )

    assert len(children) == 2
    assert all(isinstance(c, SkillGenome) for c in children)
    assert all(c.generation == 1 for c in children)
    for child in children:
        assert parent1.id in child.parent_ids or parent2.id in child.parent_ids


async def test_breed_next_gen_includes_learning_log_in_prompt():
    """Learning log marker must appear in the prompt sent to Claude."""
    import json as _json

    parent = _make_parent_genome("parent-skill", generation=0)
    child = _valid_skill_json("child-skill")
    fake_text = _json.dumps([child])

    captured_prompts: list[str] = []

    async def capturing_generate(prompt: str) -> str:
        captured_prompts.append(prompt)
        return fake_text

    with patch("skillforge.agents.spawner._generate", side_effect=capturing_generate):
        await breed_next_gen(
            parents=[parent],
            learning_log=["LOG_MARKER_XYZ"],
            breeding_instructions="Breed 1 child.",
        )

    assert captured_prompts
    assert "LOG_MARKER_XYZ" in captured_prompts[0]


# ---------------------------------------------------------------------------
# Breeder tests (Step 6e)
# ---------------------------------------------------------------------------

from skillforge.agents.breeder import (  # noqa: E402
    breed,
    compute_slots,
    publish_findings_to_bible,
    rank_skills,
)
from skillforge.models import Generation  # noqa: E402


def _breeder_skill(
    sk_id: str,
    fitness: float,
    *,
    pareto_optimal: bool = False,
    traits: list[str] | None = None,
) -> SkillGenome:
    """Helper: populated SkillGenome for Breeder tests."""
    return SkillGenome(
        id=sk_id,
        generation=0,
        skill_md_content=_valid_skill_json(name=f"skill-{sk_id[:6]}") if False else (
            # Inline a valid minimal SKILL.md
            "---\n"
            f"name: skill-{sk_id[:6]}\n"
            "description: Does things. Use when you need things done, even if not asked.\n"
            "---\n\n"
            "# Skill\n\n## Quick start\nDo the thing.\n\n"
            "**Example 1:** x / y\n**Example 2:** a / b\n"
        ),
        traits=traits or ["concise", "structured"],
        pareto_objectives={"correctness": fitness, "quality": fitness},
        is_pareto_optimal=pareto_optimal,
        trait_attribution={"concise": 0.4, "structured": 0.3},
        trait_diagnostics={"concise": "worked", "structured": "helped"},
    )


def _breeder_generation(n_skills: int = 5) -> Generation:
    """Helper: Generation with N skills at varying fitness."""
    skills = []
    for i in range(n_skills):
        fitness = 0.9 - i * 0.1  # 0.9, 0.8, 0.7, ...
        is_pareto = i < 2  # top 2 are Pareto-optimal
        skills.append(
            _breeder_skill(
                f"sk-{i:02d}-{'x' * 8}",
                fitness=fitness,
                pareto_optimal=is_pareto,
            )
        )
    return Generation(
        number=0,
        skills=skills,
        results=[],
        best_fitness=0.9,
        avg_fitness=0.7,
        pareto_front=[s.id for s in skills[:2]],
    )


# --- compute_slots -----------------------------------------------------------


@pytest.mark.parametrize(
    "pop,expected",
    [
        (3, {"elitism": 1, "wildcards": 1, "diagnostic": 0, "crossover": 1}),
        (5, {"elitism": 2, "wildcards": 1, "diagnostic": 1, "crossover": 1}),
        (10, {"elitism": 4, "wildcards": 1, "diagnostic": 2, "crossover": 3}),
        (20, {"elitism": 8, "wildcards": 2, "diagnostic": 5, "crossover": 5}),
    ],
)
def test_compute_slots_matches_plan_examples(pop, expected):
    """The worked examples from PLAN.md §Step 6e must hold exactly."""
    slots = compute_slots(pop)
    assert slots == expected
    assert sum(slots.values()) == pop


def test_compute_slots_rejects_zero():
    with pytest.raises(ValueError, match=">=1"):
        compute_slots(0)


def test_compute_slots_handles_pop_size_2():
    slots = compute_slots(2)
    assert sum(slots.values()) == 2


# --- rank_skills -------------------------------------------------------------


def test_rank_skills_pareto_optimal_first():
    gen = _breeder_generation(n_skills=5)
    ranked = rank_skills(gen)
    # Top 2 should be Pareto-optimal
    assert ranked[0].is_pareto_optimal
    assert ranked[1].is_pareto_optimal
    assert not ranked[2].is_pareto_optimal


def test_rank_skills_within_group_sorted_by_fitness():
    gen = _breeder_generation(n_skills=5)
    ranked = rank_skills(gen)
    # Within Pareto-optimal group, higher fitness first
    p0 = ranked[0].pareto_objectives["correctness"]
    p1 = ranked[1].pareto_objectives["correctness"]
    assert p0 >= p1


# --- breed() end-to-end ------------------------------------------------------


async def test_breed_produces_exact_target_pop_size():
    """Slot allocation + pad guarantee children count == target."""
    gen = _breeder_generation(n_skills=5)

    with (
        patch("skillforge.agents.breeder.breed_next_gen") as mock_breed,
        patch("skillforge.agents.breeder.spawn_gen0") as mock_spawn,
        patch("skillforge.agents.breeder._extract_lessons_and_report") as mock_extract,
    ):
        mock_breed.return_value = [_breeder_skill(f"child-{i}-xxxxxxxx", 0.5) for i in range(3)]
        mock_spawn.return_value = [_breeder_skill("wild-xxxxxxxx", 0.5)]
        mock_extract.return_value = (["lesson 1"], "breeding report text")

        children, lessons, report = await breed(
            generation=gen,
            learning_log=["old lesson"],
            specialization="test",
            target_pop_size=5,
        )

    assert len(children) == 5
    assert lessons == ["lesson 1"]
    assert "breeding report" in report


async def test_breed_elites_carry_forward_with_bumped_metadata():
    gen = _breeder_generation(n_skills=5)

    with (
        patch("skillforge.agents.breeder.breed_next_gen") as mock_breed,
        patch("skillforge.agents.breeder.spawn_gen0") as mock_spawn,
        patch("skillforge.agents.breeder._extract_lessons_and_report") as mock_extract,
    ):
        mock_breed.return_value = []
        mock_spawn.return_value = []
        mock_extract.return_value = ([], "")

        children, _, _ = await breed(
            generation=gen,
            learning_log=[],
            specialization="test",
            target_pop_size=5,
        )

    # First 2 children should be elites (from Pareto-optimal top 2)
    elite_children = [c for c in children if c.mutations == ["elitism"]]
    assert len(elite_children) >= 2
    for elite in elite_children:
        assert elite.generations_survived >= 1


async def test_breed_stamps_next_generation_number():
    gen = _breeder_generation(n_skills=5)
    gen.number = 4  # current gen is 4

    with (
        patch("skillforge.agents.breeder.breed_next_gen") as mock_breed,
        patch("skillforge.agents.breeder.spawn_gen0") as mock_spawn,
        patch("skillforge.agents.breeder._extract_lessons_and_report") as mock_extract,
    ):
        mock_breed.return_value = [_breeder_skill(f"child-{i}-xxxxxxxx", 0.5) for i in range(3)]
        mock_spawn.return_value = [_breeder_skill("wild-xxxxxxxx", 0.5)]
        mock_extract.return_value = ([], "")

        children, _, _ = await breed(
            generation=gen,
            learning_log=[],
            specialization="test",
            target_pop_size=5,
        )

    # Every child should be on generation 5
    assert all(c.generation == 5 for c in children)


async def test_breed_handles_subagent_failures_with_padding():
    """If spawner calls fail, pad with cloned elites to hit target_pop_size."""
    gen = _breeder_generation(n_skills=5)

    with (
        patch(
            "skillforge.agents.breeder.breed_next_gen",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "skillforge.agents.breeder.spawn_gen0",
            side_effect=RuntimeError("boom"),
        ),
        patch("skillforge.agents.breeder._extract_lessons_and_report") as mock_extract,
    ):
        mock_extract.return_value = ([], "")

        children, _, _ = await breed(
            generation=gen,
            learning_log=[],
            specialization="test",
            target_pop_size=5,
        )

    # Should still have exactly 5 (padded with elite clones)
    assert len(children) == 5


# --- publish_findings_to_bible ------------------------------------------------


def test_publish_findings_writes_files(tmp_path, monkeypatch):
    """Findings should land in bible/findings/ with numbered filenames."""
    # Redirect BIBLE_DIR to a temp location
    import skillforge.agents.breeder as breeder_mod

    fake_bible = tmp_path / "bible"
    (fake_bible / "findings").mkdir(parents=True)
    monkeypatch.setattr(breeder_mod, "BIBLE_DIR", fake_bible)

    publish_findings_to_bible(
        new_entries=[
            "Imperative phrasing was followed 80% more than descriptive phrasing",
            "Skills with 3 examples outperformed skills with 2 examples by 15%",
        ],
        run_id="run-12345678",
        generation=2,
    )

    files = sorted((fake_bible / "findings").glob("*.md"))
    assert len(files) == 2
    # Check naming convention
    assert files[0].name.startswith("001-")
    assert files[1].name.startswith("002-")
    # Content should contain the finding text + metadata
    content = files[0].read_text()
    assert "Finding 001" in content
    assert "run-12345678" in content
    assert "Generation" in content


def test_publish_findings_auto_increments_from_existing(tmp_path, monkeypatch):
    """If findings/005-*.md exists, next finding should be 006."""
    import skillforge.agents.breeder as breeder_mod

    fake_bible = tmp_path / "bible"
    findings = fake_bible / "findings"
    findings.mkdir(parents=True)
    (findings / "003-existing.md").write_text("pre-existing")
    (findings / "005-existing.md").write_text("pre-existing")
    monkeypatch.setattr(breeder_mod, "BIBLE_DIR", fake_bible)

    publish_findings_to_bible(
        new_entries=["New lesson"],
        run_id="run-x",
        generation=1,
    )

    files = sorted(findings.glob("*.md"))
    # Should be: 003-existing, 005-existing, 006-new-lesson
    names = [f.name for f in files]
    assert any(n.startswith("006-") for n in names)


def test_publish_findings_skips_error_placeholders(tmp_path, monkeypatch):
    """Entries starting with '(' (error placeholders) are skipped."""
    import skillforge.agents.breeder as breeder_mod

    fake_bible = tmp_path / "bible"
    (fake_bible / "findings").mkdir(parents=True)
    monkeypatch.setattr(breeder_mod, "BIBLE_DIR", fake_bible)

    publish_findings_to_bible(
        new_entries=[
            "(lesson extraction failed: boom)",
            "A real finding worth publishing",
        ],
        run_id="run-x",
        generation=1,
    )

    files = list((fake_bible / "findings").glob("*.md"))
    assert len(files) == 1  # only the real finding


def test_publish_findings_appends_to_evolution_log(tmp_path, monkeypatch):
    import skillforge.agents.breeder as breeder_mod

    fake_bible = tmp_path / "bible"
    (fake_bible / "findings").mkdir(parents=True)
    log_path = fake_bible / "evolution-log.md"
    log_path.write_text("# Evolution Log\n\n")
    monkeypatch.setattr(breeder_mod, "BIBLE_DIR", fake_bible)

    publish_findings_to_bible(
        new_entries=["Lesson A"],
        run_id="run-abcdef01",
        generation=3,
    )

    content = log_path.read_text()
    assert "run-abcdef01"[:8] in content or "abcdef01" in content
    assert "gen 3" in content


def test_publish_findings_handles_empty_list(tmp_path, monkeypatch):
    import skillforge.agents.breeder as breeder_mod

    fake_bible = tmp_path / "bible"
    (fake_bible / "findings").mkdir(parents=True)
    monkeypatch.setattr(breeder_mod, "BIBLE_DIR", fake_bible)

    # Should not raise or write anything
    publish_findings_to_bible(new_entries=[], run_id="run-x", generation=0)
    assert list((fake_bible / "findings").glob("*.md")) == []
