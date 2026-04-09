"""Upload endpoint — accept a user's existing SKILL.md or Skill directory.

Accepts either:
  - A single `.md` file (interpreted as SKILL.md; no supporting files)
  - A `.zip` containing a Skill directory (SKILL.md at root + optional
    references/, scripts/, assets/)

Validates via the existing `validate_skill_structure()` and caches the parsed
genome in memory keyed by a UUID. The caller then hits POST /api/evolve/from-parent
with that upload_id to kick off an evolution run.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from dataclasses import dataclass

from fastapi import APIRouter, File, HTTPException, UploadFile

from skillforge.engine.sandbox import validate_skill_structure
from skillforge.models import SkillGenome

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


# Module-level in-memory cache: upload_id → parsed SkillGenome
@dataclass
class _UploadRecord:
    skill: SkillGenome
    filename: str


_UPLOADS: dict[str, _UploadRecord] = {}


# Safety limits (bytes)
MAX_UPLOAD_BYTES = 1 * 1024 * 1024  # 1 MB
MAX_UNPACKED_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_FILES = 100
ALLOWED_EXT = {".md", ".sh", ".py", ".txt", ".json", ".yml", ".yaml"}


def _sniff_skill_md(zf: zipfile.ZipFile) -> tuple[str, dict[str, str]]:
    """Locate SKILL.md inside a zip and return (body, supporting_files).

    The SKILL.md is allowed at the zip root OR one directory deep (`skill-name/SKILL.md`).
    Supporting files are returned as a `{relative_path: content}` dict using paths
    rooted at the skill directory (so `scripts/foo.sh`, not `skill-name/scripts/foo.sh`).
    """
    total_unpacked = 0
    skill_md_path: str | None = None

    # Figure out where SKILL.md lives
    for name in zf.namelist():
        if name.endswith("/"):
            continue
        parts = name.split("/")
        if parts[-1] == "SKILL.md" and len(parts) <= 2:
            skill_md_path = name
            break
    if skill_md_path is None:
        raise HTTPException(
            status_code=400,
            detail="zip must contain SKILL.md at root or one directory deep",
        )

    # Derive the "skill root" prefix so we can strip it from supporting files
    prefix = (
        "/".join(skill_md_path.split("/")[:-1]) + "/" if "/" in skill_md_path else ""
    )

    skill_md_body = ""
    supporting: dict[str, str] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        # Path traversal + absolute path rejection
        if ".." in info.filename or info.filename.startswith("/"):
            raise HTTPException(
                status_code=400, detail=f"unsafe path in zip: {info.filename}"
            )
        # Compression ratio check (zip bomb protection)
        if info.compress_size > 0 and info.file_size / info.compress_size > 20:
            raise HTTPException(
                status_code=400,
                detail=f"zip entry {info.filename!r} exceeds compression ratio limit",
            )
        total_unpacked += info.file_size
        if total_unpacked > MAX_UNPACKED_BYTES:
            raise HTTPException(
                status_code=400, detail="zip unpacked size exceeds 5 MB limit"
            )
        # Strip the skill-root prefix
        rel = info.filename[len(prefix):] if info.filename.startswith(prefix) else info.filename
        if not rel:
            continue
        ext = "." + rel.rsplit(".", 1)[-1] if "." in rel else ""
        if ext not in ALLOWED_EXT:
            continue  # silently skip disallowed extensions
        try:
            content = zf.read(info.filename).decode("utf-8", errors="replace")
        except Exception:
            continue
        if rel == "SKILL.md":
            skill_md_body = content
        else:
            supporting[rel] = content

    if not skill_md_body:
        raise HTTPException(status_code=400, detail="zip did not contain a readable SKILL.md")
    return skill_md_body, supporting


@router.post("/skill")
async def upload_skill(file: UploadFile = File(...)) -> dict:
    """Upload a SKILL.md or zipped Skill directory for later fork-and-evolve."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400, detail=f"upload exceeds {MAX_UPLOAD_BYTES // 1024}KB limit"
        )

    filename = file.filename or "uploaded-skill"
    skill_md: str
    supporting: dict[str, str] = {}

    if filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                if len(zf.namelist()) > MAX_FILES:
                    raise HTTPException(
                        status_code=400, detail=f"zip contains more than {MAX_FILES} files"
                    )
                skill_md, supporting = _sniff_skill_md(zf)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="file is not a valid zip archive")
    elif filename.lower().endswith(".md"):
        try:
            skill_md = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="SKILL.md must be UTF-8")
    else:
        raise HTTPException(
            status_code=400, detail="only .md or .zip files are accepted"
        )

    # Construct an ad-hoc SkillGenome for validation
    upload_id = uuid.uuid4().hex
    genome = SkillGenome(
        id=f"upload-{upload_id}",
        generation=0,
        skill_md_content=skill_md,
        supporting_files=supporting,
        maturity="draft",
    )

    violations = validate_skill_structure(genome)
    if violations:
        return {
            "upload_id": None,
            "filename": filename,
            "valid": False,
            "errors": violations,
        }

    # Extract frontmatter for the preview response
    frontmatter_preview: dict = {}
    if skill_md.startswith("---"):
        try:
            import yaml

            _, fm_block, _ = skill_md.split("---", 2)
            parsed = yaml.safe_load(fm_block) or {}
            if isinstance(parsed, dict):
                frontmatter_preview = parsed
        except Exception:
            pass

    _UPLOADS[upload_id] = _UploadRecord(skill=genome, filename=filename)

    return {
        "upload_id": upload_id,
        "filename": filename,
        "valid": True,
        "frontmatter": frontmatter_preview,
        "skill_md_content": skill_md,
        "supporting_files": list(supporting.keys()),
    }


def get_upload(upload_id: str) -> SkillGenome | None:
    """Retrieve a previously-uploaded genome by id. Returns None if missing."""
    rec = _UPLOADS.get(upload_id)
    return rec.skill if rec else None


def clear_upload(upload_id: str) -> None:
    """Remove an upload from the cache (call after evolution starts)."""
    _UPLOADS.pop(upload_id, None)
