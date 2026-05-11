import os
import logging
import secrets
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from typing import Optional
import json

log = logging.getLogger("grantentic.database")

def get_supabase() -> Client:
    """
    Return a Supabase client authenticated with the service_role key.

    The app handles its own authentication (see src/auth.py), so every database
    call is made server-side on behalf of an already-authenticated user. We use
    service_role (which bypasses RLS) because the application layer — not
    Supabase Auth — decides which user_id a query is scoped to. The anon key
    would require a Supabase-Auth JWT (auth.uid()), which we do not issue.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment"
        )
    return create_client(url, key)

def get_user_by_username(username: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("users").select("*").eq("username", username).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None

def create_user(username: str, hashed_password: str, salt: str, is_admin: bool = False, email: str = "") -> dict:
    sb = get_supabase()
    result = sb.table("users").insert({
        "username": username,
        "hashed_password": hashed_password,
        "salt": salt,
        "is_admin": is_admin,
        "plan": "free",
        "submissions_used": 0,
        "email": email,
    }).execute()
    return result.data[0]

def update_user_plan(user_id: str, plan: str, submissions_used: int = 0) -> None:
    sb = get_supabase()
    sb.table("users").update({"plan": plan, "submissions_used": submissions_used}).eq("id", user_id).execute()

def get_company_context(user_id: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("company_contexts").select("context_json").eq("user_id", user_id).limit(1).execute()
    rows = result.data or []
    if rows:
        raw = rows[0].get("context_json")
        return json.loads(raw) if isinstance(raw, str) else raw
    return None

def save_company_context(user_id: str, context: dict) -> None:
    sb = get_supabase()
    payload = {
        "user_id": user_id,
        "context_json": json.dumps(context),
    }
    log.info(
        "save_company_context: upserting user_id=%r keys=%s json_len=%d",
        user_id, sorted(context.keys()), len(payload["context_json"]),
    )
    result = sb.table("company_contexts").upsert(
        payload, on_conflict="user_id"
    ).execute()
    log.info(
        "save_company_context: upsert returned data=%r count=%r",
        result.data, getattr(result, "count", None),
    )

def save_proposal(
    user_id: str,
    proposal_type: str,
    sections: dict,
    status: str = "draft",
    expert_review_requested: bool = False,
) -> dict:
    sb = get_supabase()
    result = sb.table("proposals").insert({
        "user_id": user_id,
        "proposal_type": proposal_type,
        "sections_json": json.dumps(sections),
        "status": status,
        "expert_review_requested": expert_review_requested,
    }).execute()
    return result.data[0]

def get_proposals_for_user(user_id: str) -> list[dict]:
    sb = get_supabase()
    result = sb.table("proposals").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    proposals = result.data or []
    for p in proposals:
        raw = p.get("sections_json")
        p["sections"] = json.loads(raw) if isinstance(raw, str) else raw
    return proposals

def get_proposal(proposal_id: str, user_id: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("proposals").select("*").eq("id", proposal_id).eq("user_id", user_id).limit(1).execute()
    rows = result.data or []
    if rows:
        row = rows[0]
        raw = row.get("sections_json")
        row["sections"] = json.loads(raw) if isinstance(raw, str) else raw
        return row
    return None

def update_proposal_status(proposal_id: str, user_id: str, status: str) -> None:
    sb = get_supabase()
    sb.table("proposals").update({"status": status}).eq("id", proposal_id).eq("user_id", user_id).execute()


# ============================================================================
# USER LOOKUP BY EMAIL
# ============================================================================

def get_user_by_email(email: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("users").select("*").eq("email", email).limit(1).execute()
    rows = result.data or []
    return rows[0] if rows else None


# ============================================================================
# PASSWORD RESET
# ============================================================================

def create_password_reset_token(user_id: str) -> str:
    sb = get_supabase()
    token = secrets.token_urlsafe(48)
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    sb.table("password_resets").insert({
        "user_id": user_id,
        "token": token,
        "expires_at": expires_at,
    }).execute()
    return token


def get_password_reset_token(token: str) -> Optional[dict]:
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    result = (
        sb.table("password_resets")
        .select("*")
        .eq("token", token)
        .eq("used", False)
        .gte("expires_at", now)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def mark_token_used(token: str) -> None:
    sb = get_supabase()
    sb.table("password_resets").update({"used": True}).eq("token", token).execute()


def update_user_password(user_id: str, hashed_password: str, salt: str) -> None:
    sb = get_supabase()
    sb.table("users").update({
        "hashed_password": hashed_password,
        "salt": salt,
    }).eq("id", user_id).execute()


# ============================================================================
# CREDITS — pre_proposal_credits + full_proposal_credits on users
# ============================================================================

def grant_credits(user_id: str, *, pre_proposal: int = 0, full_proposal: int = 0) -> None:
    """Add credits to a user. Pre-Proposal purchase grants 1 pre-proposal credit;
    Full Proposal Upfront grants 1 full-proposal credit; Option B (Success Fee)
    grants 3 full-proposal credits — the Triple Redundancy Guarantee."""
    if pre_proposal == 0 and full_proposal == 0:
        return
    sb = get_supabase()
    user = sb.table("users").select("pre_proposal_credits,full_proposal_credits").eq("id", user_id).limit(1).execute()
    rows = user.data or []
    if not rows:
        log.warning("grant_credits: user_id=%r not found", user_id)
        return
    current = rows[0]
    sb.table("users").update({
        "pre_proposal_credits":  (current.get("pre_proposal_credits")  or 0) + pre_proposal,
        "full_proposal_credits": (current.get("full_proposal_credits") or 0) + full_proposal,
    }).eq("id", user_id).execute()


def get_credits(user_id: str) -> dict:
    sb = get_supabase()
    result = sb.table("users").select("pre_proposal_credits,full_proposal_credits").eq("id", user_id).limit(1).execute()
    rows = result.data or []
    if not rows:
        return {"pre_proposal_credits": 0, "full_proposal_credits": 0}
    return {
        "pre_proposal_credits":  rows[0].get("pre_proposal_credits")  or 0,
        "full_proposal_credits": rows[0].get("full_proposal_credits") or 0,
    }


# ============================================================================
# PENDING APPROVALS (Full Proposal — Option B success-fee queue)
# ============================================================================

class StorageBucketMissingError(RuntimeError):
    """Raised when the invitation-letters bucket has not been created in
    Supabase Storage. Surface a friendly message to the user — do not crash."""


_INVITATION_BUCKET = "invitation-letters"


def upload_invitation_letter(*, object_path: str, content: bytes, content_type: str = "application/pdf") -> str:
    """Upload an invitation letter PDF to Supabase Storage and return the object path.
    Raises StorageBucketMissingError if the bucket has not been created yet."""
    sb = get_supabase()
    try:
        sb.storage.from_(_INVITATION_BUCKET).upload(
            path=object_path,
            file=content,
            file_options={"content-type": content_type, "upsert": "false"},
        )
    except Exception as exc:
        msg = str(exc).lower()
        if "bucket not found" in msg or "404" in msg or "not found" in msg:
            raise StorageBucketMissingError(
                f"Supabase Storage bucket '{_INVITATION_BUCKET}' is missing. "
                "Tom: create a private bucket with that exact name in the Supabase dashboard."
            ) from exc
        raise
    return object_path


def signed_invitation_letter_url(object_path: str, *, expires_in: int = 600) -> Optional[str]:
    """Return a short-lived signed URL for downloading an invitation letter.
    Returns None if the bucket or object is missing — admin UI shows a friendly
    error rather than crashing."""
    sb = get_supabase()
    try:
        result = sb.storage.from_(_INVITATION_BUCKET).create_signed_url(object_path, expires_in)
    except Exception as exc:
        log.warning("signed_invitation_letter_url failed for %r: %s", object_path, exc)
        return None
    if isinstance(result, dict):
        return result.get("signedURL") or result.get("signed_url")
    return None


def create_pending_approval(
    *,
    user_id: Optional[str],
    contact_email: str,
    product: str,
    invitation_letter_path: str,
    invitation_letter_name: Optional[str],
) -> dict:
    sb = get_supabase()
    payload = {
        "user_id": user_id,
        "contact_email": contact_email,
        "product": product,
        "invitation_letter_path": invitation_letter_path,
        "invitation_letter_name": invitation_letter_name,
        "status": "pending",
    }
    result = sb.table("pending_approvals").insert(payload).execute()
    return result.data[0]


def list_pending_approvals() -> list[dict]:
    sb = get_supabase()
    result = (
        sb.table("pending_approvals")
        .select("id,user_id,contact_email,product,invitation_letter_path,"
                "invitation_letter_name,status,requested_at,decided_at,decided_by,notes")
        .order("requested_at", desc=True)
        .limit(200)
        .execute()
    )
    return result.data or []


def get_pending_approval(approval_id: str) -> Optional[dict]:
    sb = get_supabase()
    result = (
        sb.table("pending_approvals")
        .select("*")
        .eq("id", approval_id)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else None


def decide_pending_approval(approval_id: str, status: str, decided_by: str) -> None:
    if status not in ("approved", "rejected"):
        raise ValueError(f"invalid status: {status}")
    sb = get_supabase()
    sb.table("pending_approvals").update({
        "status": status,
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": decided_by,
    }).eq("id", approval_id).execute()
