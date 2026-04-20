"""Skill lifecycle — upload, archive, and archive-safe helpers.

All the SDK quirks called out in the package docstring (folder name
matching frontmatter, 3-step delete dance, never-delete-Anthropic-skills
guard, BOM normalization) live here.
"""

from __future__ import annotations

import re

from anthropic import AsyncAnthropic

from skillforge.agents.managed_agents._constants import ANTHROPIC_SKILL_SOURCE, SKILLS_BETA

# ---------------------------------------------------------------------------
# Skill upload + 3-step delete dance
# ---------------------------------------------------------------------------


async def upload_skill(
    client: AsyncAnthropic,
    *,
    name: str,
    skill_md: str,
) -> str:
    """Upload a SKILL.md as a versioned org-level custom skill.

    Two empirical constraints from Step 0:

      1. The file must live inside a top-level folder — passing a bare
         ``SKILL.md`` filename returns ``400 SKILL.md file must be exactly
         in the top-level folder.``
      2. **The folder name must MATCH the ``name:`` field in the SKILL.md
         frontmatter** — surfaced during the live end-to-end smoke. The
         ``name`` argument to this function is therefore IGNORED for the
         folder/upload — we always extract the actual frontmatter name and
         use that. The ``name`` arg is still used as the ``display_title``
         (which can be anything human-readable).

    The Anthropic Skills API hard-requires the payload to start literally
    with ``---``. A UTF-8 BOM or stray leading whitespace — which neither
    our structural validator nor JSON round-tripping strips — is enough
    to earn a ``400 SKILL.md must start with YAML frontmatter (---)``.
    We normalize here so the ~1% of model outputs with a leading BOM or
    whitespace still upload cleanly instead of falling back to inline.

    Returns the new ``skill_id``. The caller is responsible for archiving it
    via :func:`archive_skill` after the session completes.
    """
    # Strip leading BOM + whitespace the API is strict about; don't touch
    # the rest of the body so checksum/fitness stays stable.
    normalized = skill_md.lstrip("\ufeff \t\r\n")
    if not normalized.startswith("---"):
        raise ValueError(
            "upload_skill: skill_md does not start with YAML frontmatter (---) "
            "after stripping BOM/whitespace — refusing to call the API"
        )
    folder = _extract_skill_name_from_md(normalized) or name
    resp = await client.beta.skills.create(
        display_title=name,
        files=[
            (
                f"{folder}/SKILL.md",
                normalized.encode("utf-8"),
                "text/markdown",
            )
        ],
        betas=[SKILLS_BETA],
    )
    return resp.id


_SKILL_NAME_RE = re.compile(r"^name:\s*(?P<name>[^\s\n]+)\s*$", re.MULTILINE)


def _extract_skill_name_from_md(skill_md: str) -> str | None:
    """Pull the ``name`` field out of a SKILL.md's YAML frontmatter.

    Robust to variations in YAML formatting — uses a simple regex against
    the raw text instead of parsing YAML, because the API's matching is
    string-literal so we want exactly what's in the file. Returns None
    if no name field is found.
    """
    if not skill_md.startswith("---"):
        return None
    try:
        _, fm_block, _ = skill_md.split("---", 2)
    except ValueError:
        return None
    match = _SKILL_NAME_RE.search(fm_block)
    if not match:
        return None
    return match.group("name").strip()


async def archive_skill(client: AsyncAnthropic, skill_id: str) -> None:
    """Tear down a custom skill via the 3-step delete dance.

    Steps:
      1. ``versions.list(skill_id)`` — paginator over version objects
      2. ``versions.delete(version=ver_str, skill_id=skill_id)`` for each
      3. ``skills.delete(skill_id)``

    **Anthropic built-in skills are protected**: we never list or delete
    a skill we did not upload. The caller is responsible for passing
    only ``skill_id``s that came from :func:`upload_skill`. As a
    belt-and-suspenders, we re-fetch the skill via ``retrieve`` and
    refuse to proceed if its ``source`` is ``anthropic``.

    Best-effort: any error in the dance is raised so the caller can log
    a leak in the ``leaked_skills`` table. Use :func:`archive_skill_safe`
    if you want a swallow-and-log variant.
    """
    # Built-in guard
    try:
        existing = await client.beta.skills.retrieve(skill_id, betas=[SKILLS_BETA])
        source = getattr(existing, "source", None)
        if source == ANTHROPIC_SKILL_SOURCE:
            raise PermissionError(
                f"refusing to archive Anthropic built-in skill {skill_id} "
                f"(source={source!r})"
            )
    except PermissionError:
        raise
    except Exception:  # noqa: BLE001
        # If retrieve fails (skill already gone? auth issue?), proceed —
        # the delete dance will surface a clearer error if there's a
        # real problem.
        pass

    # Step 1+2: enumerate and delete versions
    versions_page = await client.beta.skills.versions.list(
        skill_id, betas=[SKILLS_BETA]
    )
    async for version in versions_page:
        ver = getattr(version, "version", None)
        if ver is None and hasattr(version, "model_dump"):
            ver = version.model_dump().get("version")
        if ver is None:
            continue
        await client.beta.skills.versions.delete(
            version=str(ver),
            skill_id=skill_id,
            betas=[SKILLS_BETA],
        )

    # Step 3: delete the skill itself
    await client.beta.skills.delete(skill_id, betas=[SKILLS_BETA])


async def archive_skill_safe(
    client: AsyncAnthropic,
    skill_id: str,
) -> tuple[bool, str | None]:
    """Swallow-and-log variant. Returns ``(success, error_message)``."""
    try:
        await archive_skill(client, skill_id)
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, f"{exc.__class__.__name__}: {str(exc)[:300]}"


