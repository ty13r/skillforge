"""Invite gating — code validation + email request capture.

The real evolve endpoints (/api/evolve and /api/evolve/from-parent) require
a valid code from the ``SKILLFORGE_INVITE_CODES`` env allowlist. Users
without a code can submit an email via POST /api/invites/request; this
logs the request to the ``invite_requests`` table but does NOT grant any
access. Matt reviews the table manually and sends codes out-of-band.

The demo endpoint (/api/debug/fake-run) is NOT gated — the public demo
stays open so visitors can see the app work without an invite.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

import aiosqlite
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from skillforge.config import ADMIN_TOKEN, DB_PATH, INVITE_CODES, invite_code_valid

router = APIRouter(prefix="/api/invites", tags=["invites"])


class ValidateRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=64)


class ValidateResponse(BaseModel):
    valid: bool
    gating_enabled: bool


class InviteRequestPayload(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    message: str | None = Field(default=None, max_length=1000)


class InviteRequestRecord(BaseModel):
    id: str
    email: str
    message: str | None
    created_at: str
    status: str
    notes: str | None


@router.post("/validate", response_model=ValidateResponse)
async def validate(req: ValidateRequest) -> ValidateResponse:
    """Check whether a code is in the allowlist.

    Returns ``valid=True`` when the code matches (case-insensitive, trimmed)
    OR when gating is disabled (empty ``SKILLFORGE_INVITE_CODES``). The
    frontend stores the code in localStorage on success and sends it with
    every subsequent evolve request.
    """
    return ValidateResponse(
        valid=invite_code_valid(req.code),
        gating_enabled=bool(INVITE_CODES),
    )


@router.get("/status")
async def status() -> dict:
    """Report whether gating is enabled + how many codes were loaded.

    The ``codes_loaded`` count is safe to expose (no values) and useful
    for diagnosing env-var injection issues on hosting platforms.
    """
    return {
        "gating_enabled": bool(INVITE_CODES),
        "codes_loaded": len(INVITE_CODES),
    }


@router.post("/request")
async def request_invite(payload: InviteRequestPayload) -> dict:
    """Log an invite request. Does NOT grant access.

    The request lands in the ``invite_requests`` table with status='pending'.
    Matt reviews and sends codes out-of-band. The frontend shows a thank-you
    message after this call but does NOT unlock the /new page — the user
    still needs to receive a code and enter it.
    """
    # Dead-simple email validator (pydantic EmailStr catches most bad inputs)
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", payload.email):
        raise HTTPException(status_code=400, detail="invalid email")

    request_id = uuid.uuid4().hex
    now = datetime.now(UTC).isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO invite_requests (id, email, message, created_at, status)
            VALUES (?, ?, ?, ?, 'pending')
            """,
            (request_id, payload.email, payload.message, now),
        )
        await conn.commit()

    return {"ok": True, "id": request_id}


@router.get("/requests", response_model=list[InviteRequestRecord])
async def list_requests(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> list[InviteRequestRecord]:
    """List every pending invite request. Gated by ``SKILLFORGE_ADMIN_TOKEN``.

    Matt hits this to see who's asking; sends codes out-of-band via email.
    """
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="admin token required")

    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT id, email, message, created_at, status, notes "
            "FROM invite_requests ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()

    return [
        InviteRequestRecord(
            id=row["id"],
            email=row["email"],
            message=row["message"],
            created_at=row["created_at"],
            status=row["status"],
            notes=row["notes"],
        )
        for row in rows
    ]
