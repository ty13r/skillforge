"""L2 — Trigger accuracy via single batched Anthropic API call per Skill.

Given the Skill's description and a list of should_trigger / should_not_trigger
eval queries, makes ONE Messages API call that asks the model which queries
would trigger the Skill. Computes precision and recall from the result.

This avoids the naive "spawn an Agent SDK query per eval query" approach
(~150 extra SDK calls per generation). Batched call is ~30× cheaper.
"""

from __future__ import annotations

import re

from anthropic import AsyncAnthropic

from skillforge.config import ANTHROPIC_API_KEY, model_for
from skillforge.models import SkillGenome


async def run_l2(
    skill: SkillGenome,
    should_trigger: list[str],
    should_not_trigger: list[str],
) -> tuple[float, float]:
    """Return (precision, recall) for the Skill's description routing accuracy.

    Makes a single batched Anthropic API call asking the model which of the
    provided prompts would trigger the Skill, then computes precision and
    recall from the classification.

    Precision: TP / (TP + FP) — of the prompts the model said would trigger,
        how many actually should have.
    Recall: TP / (TP + FN) — of the prompts that should trigger, how many did.
    """
    # Extract the description from the SKILL.md frontmatter
    description = _extract_description(skill.skill_md_content)
    if not description:
        # No description to judge — degenerate case
        return (0.0, 0.0)

    # Build a single prompt with all eval queries numbered
    all_prompts = list(should_trigger) + list(should_not_trigger)
    if not all_prompts:
        return (0.0, 0.0)

    numbered = "\n".join(f"{i + 1}. {p}" for i, p in enumerate(all_prompts))
    user_prompt = (
        f"Skill description:\n\"\"\"{description}\"\"\"\n\n"
        f"For each user prompt below, answer Y or N whether the Claude Agent SDK "
        f"would load and invoke this Skill based solely on the description above. "
        f"A 'Y' means the description matches the user's intent; 'N' means it doesn't.\n\n"
        f"Prompts:\n{numbered}\n\n"
        f"Respond with EXACTLY one line per prompt in the format:\n"
        f"1. Y\n2. N\n3. Y\n...\n"
        f"No explanation, no prose."
    )

    client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=model_for("l2_trigger"),
        max_tokens=len(all_prompts) * 10 + 100,  # ~10 tokens per Y/N line
        messages=[{"role": "user", "content": user_prompt}],
    )

    # Parse response
    text = response.content[0].text if response.content else ""
    predictions = _parse_yn_response(text, len(all_prompts))

    n_trigger = len(should_trigger)
    tp = sum(1 for i in range(n_trigger) if predictions[i] == "Y")
    fn = n_trigger - tp
    fp = sum(1 for i in range(n_trigger, len(all_prompts)) if predictions[i] == "Y")
    # tn = len(should_not_trigger) - fp  (unused, but correct)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    return (precision, recall)


def _extract_description(skill_md_content: str) -> str:
    """Pull the 'description' field from a SKILL.md's YAML frontmatter.

    Returns empty string on any parse failure.
    """
    if not skill_md_content.startswith("---"):
        return ""
    try:
        _, fm_block, _ = skill_md_content.split("---", 2)
    except ValueError:
        return ""
    import yaml
    try:
        fm = yaml.safe_load(fm_block) or {}
    except yaml.YAMLError:
        return ""
    desc = fm.get("description", "")
    return desc if isinstance(desc, str) else ""


def _parse_yn_response(text: str, expected_count: int) -> list[str]:
    """Parse the numbered Y/N response from the model.

    Returns a list of length ``expected_count`` with values 'Y' or 'N'.
    Missing or malformed lines default to 'N' (conservative — don't reward
    a Skill that can't be classified).
    """
    predictions: list[str | None] = [None] * expected_count
    # Match lines like "1. Y" or "1) N" or "1: Y" (robust to formatting drift)
    pattern = re.compile(r"^\s*(\d+)[.:)\s]+([YN])", re.MULTILINE | re.IGNORECASE)
    for match in pattern.finditer(text):
        idx = int(match.group(1)) - 1
        answer = match.group(2).upper()
        if 0 <= idx < expected_count:
            predictions[idx] = answer
    return [p or "N" for p in predictions]
