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

def save_proposal(user_id: str, proposal_type: str, sections: dict, status: str = "draft") -> dict:
    sb = get_supabase()
    result = sb.table("proposals").insert({
        "user_id": user_id,
        "proposal_type": proposal_type,
        "sections_json": json.dumps(sections),
        "status": status
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
