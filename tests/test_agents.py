"""Agent tests: Challenge Designer, Spawner, Competitor, Breeder (Step 6)."""

from unittest.mock import patch

import pytest

claude_agent_sdk = pytest.importorskip("claude_agent_sdk")

from skillforge.agents.challenge_designer import design_challenges  # noqa: E402
from skillforge.agents.spawner import breed_next_gen, spawn_gen0  # noqa: E402
from skillforge.engine.sandbox import validate_skill_structure  # noqa: E402
from skillforge.models import Challenge, SkillGenome  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeMessage:
    """Minimal stand-in for Agent SDK message objects."""

    def __init__(self, text: str):
        # The real SDK messages have content blocks; we mock the shape our
        # extractor actually reads. Store text on a .text attribute AND on
        # .content as a list of objects with .text, so whichever path the
        # implementation uses will work.
        self.text = text

        # Match the claude_agent_sdk.AssistantMessage shape: .content is a
        # list of content blocks with .text
        class _Block:
            def __init__(self, t: str) -> None:
                self.text = t

        self.content = [_Block(text)]


async def _fake_query_from(messages: list[str]):
    """Async generator that yields FakeMessage objects for each text."""
    for text in messages:
        yield FakeMessage(text)


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


@pytest.mark.asyncio
async def test_design_challenges_returns_n_challenges():
    """Happy path: fenced JSON block → 3 challenges."""
    fake_msg_text = f"Here are the challenges:\n```json\n{_THREE_CHALLENGES_JSON}\n```"

    with patch("skillforge.agents.challenge_designer.query") as mock_query:
        mock_query.return_value = _fake_query_from([fake_msg_text])
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    assert len(challenges) == 3
    assert all(isinstance(c, Challenge) for c in challenges)
    assert {c.difficulty for c in challenges} == {"easy", "medium", "hard"}
    assert all(c.id for c in challenges)  # UUIDs populated


@pytest.mark.asyncio
async def test_design_challenges_accepts_bare_json_array():
    """No ```json fence — just a bare JSON array in the response."""
    bare_text = _THREE_CHALLENGES_JSON.strip()

    with patch("skillforge.agents.challenge_designer.query") as mock_query:
        mock_query.return_value = _fake_query_from([bare_text])
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    assert len(challenges) == 3
    assert all(isinstance(c, Challenge) for c in challenges)


@pytest.mark.asyncio
async def test_design_challenges_retries_on_parse_failure():
    """First response is garbage; second is valid. Mock called twice."""
    good_text = f"```json\n{_THREE_CHALLENGES_JSON}\n```"

    call_count = 0

    def _side_effect_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_query_from(["This is not JSON at all!"])
        else:
            return _fake_query_from([good_text])

    with patch(
        "skillforge.agents.challenge_designer.query", side_effect=_side_effect_query
    ):
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    assert call_count == 2
    assert len(challenges) == 3
    assert all(isinstance(c, Challenge) for c in challenges)


@pytest.mark.asyncio
async def test_design_challenges_raises_on_repeated_parse_failure():
    """Both attempts return garbage → ValueError with a clear message."""

    def _garbage_query(*args, **kwargs):
        return _fake_query_from(["not json at all"])

    with patch(
        "skillforge.agents.challenge_designer.query", side_effect=_garbage_query
    ), pytest.raises(ValueError, match="2 attempts"):
        await design_challenges("Elixir LiveView specialist", n=3)


@pytest.mark.asyncio
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

    with patch("skillforge.agents.challenge_designer.query") as mock_query:
        mock_query.return_value = _fake_query_from([fake_text])
        with pytest.raises(ValueError, match="expected 3"):
            await design_challenges("Elixir LiveView specialist", n=3)


@pytest.mark.asyncio
async def test_design_challenges_generates_unique_ids():
    """All returned Challenges have distinct UUIDs."""
    fake_text = f"```json\n{_THREE_CHALLENGES_JSON}\n```"

    with patch("skillforge.agents.challenge_designer.query") as mock_query:
        mock_query.return_value = _fake_query_from([fake_text])
        challenges = await design_challenges("Elixir LiveView specialist", n=3)

    ids = [c.id for c in challenges]
    assert len(ids) == len(set(ids)), "UUIDs must be unique across all challenges"


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


@pytest.mark.asyncio
async def test_spawn_gen0_returns_valid_population():
    """Happy path: mock query returns 3 valid skills → 3 SkillGenome objects."""
    skills = [_valid_skill_json(f"skill-{i}") for i in range(3)]
    import json as _json
    fake_text = _json.dumps(skills)

    with patch("skillforge.agents.spawner.query") as mock_query:
        mock_query.return_value = _fake_query_from([fake_text])
        population = await spawn_gen0("Elixir specialist", pop_size=3)

    assert len(population) == 3
    assert all(isinstance(g, SkillGenome) for g in population)
    assert all(g.generation == 0 for g in population)
    # All must pass validation
    for genome in population:
        violations = validate_skill_structure(genome)
        assert violations == [], f"Genome {genome.id} has violations: {violations}"
    # All IDs must be unique
    ids = [g.id for g in population]
    assert len(ids) == len(set(ids)), "Genome IDs must be unique"


@pytest.mark.asyncio
async def test_spawn_gen0_reads_bible_patterns():
    """System prompt must include bible pattern content."""
    import json as _json

    skills = [_valid_skill_json("my-skill")]
    fake_text = _json.dumps(skills)
    captured_prompts: list[str] = []

    def _capturing_query(prompt: str, options=None):
        captured_prompts.append(prompt)
        return _fake_query_from([fake_text])

    with patch("skillforge.agents.spawner._read_bible_patterns", return_value="PATTERN_MARKER_ABC"), \
         patch("skillforge.agents.spawner.query", side_effect=_capturing_query):
        await spawn_gen0("test domain", pop_size=1)

    assert captured_prompts, "query should have been called"
    assert "PATTERN_MARKER_ABC" in captured_prompts[0], (
        "Bible pattern marker must appear in the system prompt"
    )


@pytest.mark.asyncio
async def test_spawn_gen0_handles_missing_bible_dir(tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """spawn_gen0 works even if BIBLE_DIR doesn't exist."""
    import json as _json  # noqa: PLC0415,I001
    import skillforge.agents.spawner as spawner_mod  # noqa: PLC0415,I001

    # Point BIBLE_DIR at a nonexistent path
    monkeypatch.setattr(spawner_mod, "BIBLE_DIR", tmp_path / "nonexistent-bible-dir")

    # _read_bible_patterns should return empty string
    result = spawner_mod._read_bible_patterns()
    assert result == ""

    # spawn_gen0 should still work
    skills = [_valid_skill_json("my-skill")]
    fake_text = _json.dumps(skills)

    with patch("skillforge.agents.spawner.query") as mock_query:
        mock_query.return_value = _fake_query_from([fake_text])
        population = await spawn_gen0("test domain", pop_size=1)

    assert len(population) == 1
    assert population[0].generation == 0


@pytest.mark.asyncio
async def test_spawn_gen0_retries_on_invalid_skill():
    """First response has 1 invalid skill; second response fixes all. Assert 2 query calls."""
    import json as _json

    # Valid skill for reference
    valid_skill = _valid_skill_json("good-skill")

    # Invalid skill (missing frontmatter entirely)
    invalid_skill = {
        "name": "bad-skill",
        "skill_md_content": "# No frontmatter — this will fail validation",
        "supporting_files": {},
        "traits": [],
        "meta_strategy": "",
    }

    # Two valid skills for the retry
    retry_skills = [_valid_skill_json("fixed-skill-1"), _valid_skill_json("fixed-skill-2")]

    call_count = 0

    def _side_effect_query(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _fake_query_from([_json.dumps([valid_skill, invalid_skill])])
        else:
            return _fake_query_from([_json.dumps(retry_skills)])

    with patch("skillforge.agents.spawner.query", side_effect=_side_effect_query):
        population = await spawn_gen0("test domain", pop_size=2)

    assert call_count == 2, "Should have called query twice (initial + retry)"
    assert len(population) >= 1
    for genome in population:
        assert validate_skill_structure(genome) == []


@pytest.mark.asyncio
async def test_spawn_gen0_raises_on_persistent_invalid():
    """Both attempts return invalid skills → ValueError with violations in message."""
    import json as _json

    bad_skill = {
        "name": "bad-skill",
        "skill_md_content": "# No frontmatter — always invalid",
        "supporting_files": {},
        "traits": [],
        "meta_strategy": "",
    }

    def _bad_query(*args, **kwargs):
        return _fake_query_from([_json.dumps([bad_skill])])

    with patch("skillforge.agents.spawner.query", side_effect=_bad_query), \
         pytest.raises(ValueError, match="invalid skills after retry"):
        await spawn_gen0("test domain", pop_size=1)


# ===========================================================================
# Spawner tests — breed_next_gen
# ===========================================================================


@pytest.mark.asyncio
async def test_breed_next_gen_sets_parent_ids_and_generation():
    """Children must have generation=1 and parent_ids matching the parents."""
    import json as _json

    parent1 = _make_parent_genome("parent-one", generation=0)
    parent2 = _make_parent_genome("parent-two", generation=0)

    child1 = _valid_skill_json_with_parent("child-one", [parent1.id, parent2.id])
    child2 = _valid_skill_json_with_parent("child-two", [parent1.id, parent2.id])

    fake_text = _json.dumps([child1, child2])

    with patch("skillforge.agents.spawner.query") as mock_query:
        mock_query.return_value = _fake_query_from([fake_text])
        children = await breed_next_gen(
            parents=[parent1, parent2],
            learning_log=["gen0: plan-first strategy outperformed dive-in"],
            breeding_instructions="Breed 2 children mixing the parents' strategies.",
        )

    assert len(children) == 2
    assert all(isinstance(c, SkillGenome) for c in children)
    assert all(c.generation == 1 for c in children), "Children should be generation 1"
    # Each child should reference the parent IDs
    for child in children:
        assert parent1.id in child.parent_ids or parent2.id in child.parent_ids, (
            f"Child {child.id} should reference at least one parent ID"
        )


@pytest.mark.asyncio
async def test_breed_next_gen_includes_learning_log_in_prompt():
    """Learning log marker must appear in the system prompt sent to Claude."""
    import json as _json

    parent = _make_parent_genome("parent-skill", generation=0)
    child = _valid_skill_json("child-skill")
    fake_text = _json.dumps([child])

    captured_prompts: list[str] = []

    def _capturing_query(prompt: str, options=None):
        captured_prompts.append(prompt)
        return _fake_query_from([fake_text])

    with patch("skillforge.agents.spawner.query", side_effect=_capturing_query):
        await breed_next_gen(
            parents=[parent],
            learning_log=["LOG_MARKER_XYZ"],
            breeding_instructions="Breed 1 child.",
        )

    assert captured_prompts, "query should have been called"
    assert "LOG_MARKER_XYZ" in captured_prompts[0], (
        "Learning log marker must appear in the prompt sent to Claude"
    )
