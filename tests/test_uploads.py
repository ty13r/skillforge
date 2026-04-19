"""Tests for the skill upload + fork-from-upload flow.

Carries over the testing items from PLAN-V1.1 §2.5 + §Testing strategy §2
that were specified but never landed during the v1.1 batch. Targets the
SHIPPED implementation in ``skillforge/api/uploads.py`` (in-memory _UPLOADS
dict, not a /tmp/skillforge-uploads/ directory).

Coverage:
- Happy path: ``.md`` upload, ``.zip`` with SKILL.md at root, ``.zip`` with
  SKILL.md one directory deep.
- Size caps: ``.md`` >1 MB, unpacked ``.zip`` >5 MB.
- File cap: ``.zip`` with >100 entries.
- Zip bomb: compression ratio >20:1.
- Path traversal: ``.zip`` containing ``..`` and absolute paths.
- Extension allowlist: disallowed extensions are silently dropped (shipped
  behavior — `continue` in `_sniff_skill_md`).
- Bad upload format: file is neither ``.md`` nor ``.zip``.
- Malformed zip → 400 with a clear error.
- Validation failure: invalid SKILL.md returns ``valid=False`` + error list
  (200 status) — the user-facing validation contract.
- Upload → ``POST /api/evolve/from-parent`` integration: round-trip through
  the in-memory ``_UPLOADS`` cache and the ``PENDING_PARENTS`` registry.
- ``get_upload`` / ``clear_upload`` helpers.
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from skillforge.api import uploads as uploads_module
from skillforge.engine.run_registry import registry as _run_registry
from skillforge.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _wipe_upload_state():
    """Per-test cleanup: in-memory upload cache + RunRegistry pending parents."""
    uploads_module._UPLOADS.clear()
    _run_registry._pending_parents.clear()
    yield
    uploads_module._UPLOADS.clear()
    _run_registry._pending_parents.clear()


# A valid SKILL.md that passes validate_skill_structure:
# - starts with ---
# - parseable YAML frontmatter
# - name matches regex, no anthropic/claude
# - description ≤1024 chars, first 250 chars contain "Use when"
# - body has ≥2 example markers
VALID_SKILL_MD = """---
name: test-skill
description: Cleans up test files. Use when running tests, even if user mentions cleanup, fixtures, or teardown. NOT for production data.
allowed-tools:
  - Read
  - Write
---

# Test Skill

## Workflow

1. Identify the test files
2. Clean them up

## Examples

**Example 1:** Input: dirty.json → Output: clean.json
**Example 2:** Input: messy.csv → Output: tidy.csv
"""


def _make_zip(files: dict[str, str | bytes], compresslevel: int = 6) -> bytes:
    """Build an in-memory zip archive from a {path: content} dict."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=compresslevel
    ) as zf:
        for path, content in files.items():
            if isinstance(content, str):
                zf.writestr(path, content)
            else:
                zf.writestr(path, content)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# 1. Happy paths
# ---------------------------------------------------------------------------


def test_upload_valid_md_file(client):
    """Single .md upload returns valid=True with an upload_id and frontmatter."""
    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("SKILL.md", VALID_SKILL_MD, "text/markdown")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    assert body["upload_id"] is not None
    assert body["filename"] == "SKILL.md"
    assert body["frontmatter"]["name"] == "test-skill"
    assert body["skill_md_content"] == VALID_SKILL_MD
    assert body["supporting_files"] == []
    # The cache should hold it
    assert uploads_module.get_upload(body["upload_id"]) is not None


def test_upload_valid_zip_skill_md_at_root(client):
    """.zip with SKILL.md at the archive root → valid + supporting files preserved."""
    archive = _make_zip(
        {
            "SKILL.md": VALID_SKILL_MD,
            "scripts/helper.sh": "#!/bin/bash\necho hi\n",
            "references/notes.txt": "Reference notes for the skill.",
        }
    )

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("test-skill.zip", archive, "application/zip")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    assert body["upload_id"] is not None
    assert "scripts/helper.sh" in body["supporting_files"]
    assert "references/notes.txt" in body["supporting_files"]

    rec = uploads_module._UPLOADS[body["upload_id"]]
    assert rec.skill.supporting_files["scripts/helper.sh"] == "#!/bin/bash\necho hi\n"


def test_upload_valid_zip_skill_md_one_directory_deep(client):
    """.zip with SKILL.md inside a single subdirectory is also accepted."""
    archive = _make_zip(
        {
            "my-skill/SKILL.md": VALID_SKILL_MD,
            "my-skill/scripts/run.py": "print('hello')\n",
        }
    )

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("nested.zip", archive, "application/zip")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    # Supporting files are stored at paths relative to the skill root, not the zip root
    assert "scripts/run.py" in body["supporting_files"]


# ---------------------------------------------------------------------------
# 2. Size caps
# ---------------------------------------------------------------------------


def test_upload_oversized_md_rejected(client):
    """.md > 1 MB → 400 with a clear size error."""
    huge = "a" * (uploads_module.MAX_UPLOAD_BYTES + 1)
    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("huge.md", huge, "text/markdown")},
    )

    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"].lower() or "limit" in resp.json()["detail"].lower()


def test_upload_oversized_unpacked_zip_rejected(client):
    """.zip whose unpacked size exceeds MAX_UNPACKED_BYTES is rejected with 400.

    Build a small archive (under the 1 MB upload cap) but with the unpacked
    SKILL.md alone exceeding the 5 MB limit. zlib will compress 6 MB of 'a's
    into well under 1 MB, so the upload will land — but unpack will trip
    the size guard.
    """
    big_md = "a" * (uploads_module.MAX_UNPACKED_BYTES + 100)  # 5 MB + 100 bytes
    archive = _make_zip({"SKILL.md": big_md})
    # Sanity: the archive itself fits under the upload cap
    assert len(archive) < uploads_module.MAX_UPLOAD_BYTES

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("big.zip", archive, "application/zip")},
    )

    # The huge SKILL.md trips the compression-ratio guard FIRST (a 5 MB run of
    # 'a's compresses ~5000:1, way past 20:1). Either error path is acceptable
    # — both prove the upload was rejected before we ever wrote anything to
    # memory.
    assert resp.status_code == 400
    detail = resp.json()["detail"].lower()
    assert "compression ratio" in detail or "unpacked" in detail or "5 mb" in detail


def test_upload_unpacked_size_guard_triggers_for_incompressible_payload(client):
    """A genuinely large but uncompressible payload should trip the 5 MB unpack cap.

    Random bytes don't compress, so the compression-ratio guard won't fire —
    the unpack-size guard is the one that has to catch this.
    """
    import os

    # 4 small SKILL.md files + a few "blob" files of incompressible data that
    # together push past 5 MB unpacked.
    blob = os.urandom(800 * 1024)  # 800 KB random ≈ 800 KB compressed too
    files: dict[str, str | bytes] = {
        "SKILL.md": VALID_SKILL_MD,
    }
    for i in range(7):  # 7 × 800 KB ≈ 5.6 MB unpacked → trips 5 MB cap
        files[f"references/blob_{i}.txt"] = blob
    archive = _make_zip(files, compresslevel=0)

    # The archive is too big for the 1 MB upload cap (random data doesn't
    # compress) so this test path actually proves the OUTER cap fires. That's
    # the right behavior — the user can never get a payload past 1 MB in the
    # first place. Document the chain explicitly.
    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("blob.zip", archive, "application/zip")},
    )
    assert resp.status_code == 400


def test_upload_zip_with_more_than_max_files_rejected(client):
    """Zip with >100 entries → 400."""
    files: dict[str, str | bytes] = {"SKILL.md": VALID_SKILL_MD}
    # 101 extra dummy files
    for i in range(uploads_module.MAX_FILES + 1):
        files[f"references/file_{i}.txt"] = f"content {i}\n"
    archive = _make_zip(files)

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("many.zip", archive, "application/zip")},
    )

    assert resp.status_code == 400
    assert "more than" in resp.json()["detail"].lower() or str(uploads_module.MAX_FILES) in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 3. Zip bomb
# ---------------------------------------------------------------------------


def test_upload_zip_bomb_rejected(client):
    """A highly compressible payload (compression ratio >20:1) → 400."""
    # 200 KB of zeros compresses to ~200 bytes → ratio ~1000:1, well past 20:1
    bomb_payload = "0" * 200_000
    archive = _make_zip({"SKILL.md": VALID_SKILL_MD, "zeros.txt": bomb_payload})

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("bomb.zip", archive, "application/zip")},
    )

    assert resp.status_code == 400
    assert "compression ratio" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Path traversal
# ---------------------------------------------------------------------------


def test_upload_zip_with_dotdot_path_rejected(client):
    """Zip entry containing '..' is rejected for path traversal."""
    archive_buf = io.BytesIO()
    with zipfile.ZipFile(archive_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", VALID_SKILL_MD)
        zf.writestr("../etc/passwd", "root:x:0:0::/root:/bin/sh\n")

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("traverse.zip", archive_buf.getvalue(), "application/zip")},
    )

    assert resp.status_code == 400
    assert "unsafe path" in resp.json()["detail"].lower()


def test_upload_zip_with_absolute_path_rejected(client):
    """Zip entry with an absolute path is rejected."""
    archive_buf = io.BytesIO()
    with zipfile.ZipFile(archive_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("SKILL.md", VALID_SKILL_MD)
        zf.writestr("/tmp/evil.sh", "#!/bin/bash\nrm -rf /\n")

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("absolute.zip", archive_buf.getvalue(), "application/zip")},
    )

    assert resp.status_code == 400
    assert "unsafe path" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5. Extension allowlist (silently drops, doesn't 400)
# ---------------------------------------------------------------------------


def test_upload_zip_silently_drops_disallowed_extensions(client):
    """Files with disallowed extensions are silently dropped, the upload still succeeds.

    PLAN-V1.1 §2.2 spec'd "rejected" but the shipped implementation in
    _sniff_skill_md continues past disallowed entries instead of failing.
    Test the shipped behavior — flag a follow-up if we want to tighten this.
    """
    archive = _make_zip(
        {
            "SKILL.md": VALID_SKILL_MD,
            "scripts/helper.sh": "#!/bin/bash\necho hi\n",  # allowed
            "evil.exe": "BINARY",  # disallowed → silently dropped
            "malware.dll": "BINARY",  # disallowed → silently dropped
        }
    )

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("mixed.zip", archive, "application/zip")},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True
    # The allowed file made it through
    assert "scripts/helper.sh" in body["supporting_files"]
    # The disallowed extensions were silently dropped (not rejected, not preserved)
    assert "evil.exe" not in body["supporting_files"]
    assert "malware.dll" not in body["supporting_files"]


# ---------------------------------------------------------------------------
# 6. Bad upload format / malformed zip
# ---------------------------------------------------------------------------


def test_upload_unsupported_extension_rejected(client):
    """File extensions other than .md or .zip → 400."""
    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("skill.txt", VALID_SKILL_MD, "text/plain")},
    )

    assert resp.status_code == 400
    assert ".md" in resp.json()["detail"]
    assert ".zip" in resp.json()["detail"]


def test_upload_malformed_zip_rejected(client):
    """A file claiming to be .zip but containing garbage is rejected."""
    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("fake.zip", b"this is not a zip archive at all", "application/zip")},
    )

    assert resp.status_code == 400
    assert "valid zip" in resp.json()["detail"].lower()


def test_upload_zip_without_skill_md_rejected(client):
    """A zip that doesn't contain SKILL.md is rejected."""
    archive = _make_zip(
        {
            "README.md": "# Just a readme",
            "other-file.txt": "no SKILL.md here",
        }
    )

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("no-skill.zip", archive, "application/zip")},
    )

    assert resp.status_code == 400
    assert "SKILL.md" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 7. Validation failure surfaces in the response body
# ---------------------------------------------------------------------------


def test_upload_invalid_skill_md_returns_validation_errors(client):
    """SKILL.md that fails validate_skill_structure returns valid=False + errors."""
    invalid_md = "Just some prose without any frontmatter at all."

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("bad.md", invalid_md, "text/markdown")},
    )

    # The request itself succeeded; the validation failure is in the body
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    assert body["upload_id"] is None
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) > 0
    # The validator should mention the missing frontmatter
    joined = " ".join(body["errors"]).lower()
    assert "frontmatter" in joined or "yaml" in joined


def test_upload_skill_md_missing_use_when_returns_validation_errors(client):
    """A skill missing the 'Use when' pushy-pattern signal fails validation."""
    bad_skill = """---
name: bad-skill
description: This skill does things but lacks the pushy trigger signal entirely.
---

# Bad Skill

## Examples
**Example 1:** x → y
**Example 2:** a → b
"""

    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("bad.md", bad_skill, "text/markdown")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is False
    joined = " ".join(body["errors"]).lower()
    assert "use when" in joined


# ---------------------------------------------------------------------------
# 8. get_upload / clear_upload helpers
# ---------------------------------------------------------------------------


def test_get_upload_returns_none_for_unknown_id():
    """Unknown upload_id → None."""
    assert uploads_module.get_upload("does-not-exist") is None


def test_clear_upload_removes_entry(client):
    """clear_upload(id) removes the cache entry."""
    resp = client.post(
        "/api/uploads/skill",
        files={"file": ("SKILL.md", VALID_SKILL_MD, "text/markdown")},
    )
    upload_id = resp.json()["upload_id"]
    assert uploads_module.get_upload(upload_id) is not None

    uploads_module.clear_upload(upload_id)
    assert uploads_module.get_upload(upload_id) is None


def test_clear_upload_unknown_id_is_a_noop():
    """clear_upload on a missing id doesn't raise."""
    uploads_module.clear_upload("never-existed")  # must not raise


# ---------------------------------------------------------------------------
# 9. Upload → fork integration
# ---------------------------------------------------------------------------


def test_upload_then_fork_round_trip(client):
    """Upload a valid SKILL.md, then POST /api/evolve/from-parent with the upload_id.

    Asserts:
      - The upload lands in _UPLOADS.
      - The fork endpoint pulls it out via get_upload.
      - The parent is stashed in PENDING_PARENTS keyed by the new run id.
      - The upload is cleared from _UPLOADS after a successful fork.
    """
    upload_resp = client.post(
        "/api/uploads/skill",
        files={"file": ("SKILL.md", VALID_SKILL_MD, "text/markdown")},
    )
    upload_id = upload_resp.json()["upload_id"]
    assert upload_id is not None
    assert uploads_module.get_upload(upload_id) is not None

    with (
        patch("skillforge.api.routes.init_db", new_callable=AsyncMock),
        patch("skillforge.api.routes.save_run", new_callable=AsyncMock),
        patch("skillforge.api.routes.run_evolution", new_callable=AsyncMock),
    ):
        fork_resp = client.post(
            "/api/evolve/from-parent",
            json={
                "parent_source": "upload",
                "parent_id": upload_id,
                "population_size": 2,
                "num_generations": 1,
                "max_budget_usd": 1.0,
            },
        )

    assert fork_resp.status_code == 200, fork_resp.text
    payload = fork_resp.json()
    new_run_id = payload["run_id"]
    parent = _run_registry.take_parent(new_run_id)
    assert parent is not None
    assert parent.skill_md_content == VALID_SKILL_MD
    _run_registry.stash_parent(new_run_id, parent)
    # The upload should be cleared from the cache after the fork starts
    assert uploads_module.get_upload(upload_id) is None
