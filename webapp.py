#!/usr/bin/env python3
"""
Grantentic - FastAPI Web Application
AI-Powered Grant Writing System for NSF, DoD, and NASA SBIR Phase I proposals

Full HTML control with FastAPI + Jinja2 + HTMX
"""

import json
import logging
import os
import secrets
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("grantentic")

# Sentry error tracking — only initialize if DSN is configured
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.2,
        environment="production",
    )
    log.info("Sentry initialized")

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import base64
import stripe

from config import Config
from src.auth import authenticate_user, register_user
from src.database import (
    get_user_by_username,
    get_user_by_email,
    get_company_context,
    save_company_context,
    save_proposal,
    get_proposals_for_user,
    get_proposal,
    create_password_reset_token,
    get_password_reset_token,
    mark_token_used,
    update_user_password,
    create_pending_approval,
    list_pending_approvals,
    get_pending_approval,
    decide_pending_approval,
    upload_invitation_letter,
    signed_invitation_letter_url,
    StorageBucketMissingError,
    grant_credits,
    get_credits,
)
from src.auth import hash_password
from src.agency_loader import load_agency_requirements
from src.models import GrantProposal, GrantSection

# Initialize Stripe
stripe.api_key = Config.STRIPE_SECRET_KEY


# Application state
class AppState:
    proposals: Dict[str, Any] = {}
    generation_tasks: Dict[str, Any] = {}


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize on startup"""
    yield


app = FastAPI(
    title="Grantentic",
    description="AI-Powered Grant Writing System",
    lifespan=lifespan
)

# Session middleware for authentication
if not Config.SECRET_KEY:
    log.warning("SECRET_KEY is not set — session cookies are insecure. Set SECRET_KEY in environment variables.")
app.add_middleware(
    SessionMiddleware,
    secret_key=Config.SECRET_KEY or "temporary-insecure-key-for-local-dev",
    max_age=3600 * 24  # 24 hours
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


# Template filters
def format_currency(value: int) -> str:
    return f"${value:,}"


def format_number(value: int) -> str:
    return f"{value:,}"


templates.env.filters["currency"] = format_currency
templates.env.filters["number"] = format_number


# Authentication dependency
def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    return request.session.get("user")


def require_auth(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_user(request: Request) -> str:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def get_agency_info(agency: str) -> Dict[str, Any]:
    """Get agency information"""
    try:
        loader = load_agency_requirements(agency)
        req = loader.requirements
        return {
            'agency': req.agency,
            'program': req.program,
            'funding_amount': req.funding_amount,
            'duration_months': req.duration_months,
            'description': req.description,
            'sections_count': len(req.sections),
            'loader': loader
        }
    except Exception as e:
        return {'error': str(e)}


# Routes

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Root: marketing landing page for anonymous visitors, dashboard for logged-in."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request, "landing.html", {"user": None})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None, success: str = None):
    """Login page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(request, "login.html", {
        "error": error,
        "success": success,
    })


@app.post("/login")
async def login(request: Request):
    """Handle login"""
    form = await request.form()
    username = form.get("username", "").strip()
    password = form.get("password", "")
    user = authenticate_user(username, password)
    if not user:
        log.info("login: auth FAILED for username=%r", username)
        return templates.TemplateResponse(request, "login.html", {
            "error": "Invalid username or password"
        })
    log.info(
        "login: auth OK for username=%r user_id=%r (type=%s) is_admin=%r",
        user["username"], user.get("id"), type(user.get("id")).__name__,
        user.get("is_admin"),
    )
    request.session["username"] = user["username"]
    request.session["user_id"] = str(user["id"])
    request.session["is_admin"] = user.get("is_admin", False)
    request.session["user"] = {"username": user["username"], "role": "admin" if user.get("is_admin") else "user"}
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Registration page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse(request, "register.html", {
        "error": None, "username": "", "email": ""
    })


@app.post("/register")
async def register(request: Request):
    """Handle registration"""
    form = await request.form()
    username = form.get("username", "").strip()
    email = form.get("email", "").strip()
    password = form.get("password", "")
    password_confirm = form.get("password_confirm", "")

    # Validation
    error = None
    if len(username) < 3:
        error = "Username must be at least 3 characters."
    elif "@" not in email:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif password != password_confirm:
        error = "Passwords do not match."

    if error:
        return templates.TemplateResponse(request, "register.html", {
            "error": error, "username": username, "email": email
        })

    try:
        register_user(username, password, email=email)
    except ValueError as exc:
        return templates.TemplateResponse(request, "register.html", {
            "error": str(exc), "username": username, "email": email
        })
    except Exception as exc:
        log.exception("register: failed for username=%r: %s", username, exc)
        return templates.TemplateResponse(request, "register.html", {
            "error": "An error occurred creating your account. Please try again.",
            "username": username, "email": email,
        })

    return RedirectResponse(url="/login?success=Account+created.+Please+sign+in.", status_code=303)


@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    """Forgot password form"""
    return templates.TemplateResponse(request, "forgot_password.html", {
        "message": None, "error": None
    })


@app.post("/forgot-password")
async def forgot_password(request: Request):
    """Handle forgot password — send reset email"""
    form = await request.form()
    email = form.get("email", "").strip()

    # Always show the same message to prevent email enumeration
    safe_message = "If that email is associated with an account, you will receive a reset link shortly."

    if email and "@" in email:
        user = get_user_by_email(email)
        if user:
            try:
                token = create_password_reset_token(str(user["id"]))
                reset_url = f"{Config.BASE_URL}/reset-password?token={token}"

                if Config.RESEND_API_KEY:
                    import resend
                    resend.api_key = Config.RESEND_API_KEY
                    resend.Emails.send({
                        "from": "Grantentic <noreply@grantentic.us>",
                        "to": [email],
                        "subject": "Reset your Grantentic password",
                        "html": (
                            f"<p>Hi {user['username']},</p>"
                            f"<p>We received a request to reset your Grantentic password.</p>"
                            f"<p>Click the link below to set a new password. This link expires in 1 hour.</p>"
                            f'<p><a href="{reset_url}">{reset_url}</a></p>'
                            f"<p>If you did not request this, you can safely ignore this email.</p>"
                            f"<p>— Grantentic</p>"
                        ),
                    })
                    log.info("forgot_password: reset email sent to %r", email)
                else:
                    log.warning("forgot_password: RESEND_API_KEY not set, token=%s", token)
            except Exception as exc:
                log.exception("forgot_password: failed to send reset email: %s", exc)

    return templates.TemplateResponse(request, "forgot_password.html", {
        "message": safe_message, "error": None
    })


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    """Reset password form — validates token first"""
    if not token:
        return templates.TemplateResponse(request, "reset_password.html", {
            "error": "Missing reset token.", "token": "", "valid": False
        })

    reset = get_password_reset_token(token)
    if not reset:
        return templates.TemplateResponse(request, "reset_password.html", {
            "error": "This reset link is invalid or has expired. Please request a new one.",
            "token": "", "valid": False
        })

    return templates.TemplateResponse(request, "reset_password.html", {
        "error": None, "token": token, "valid": True
    })


@app.post("/reset-password")
async def reset_password(request: Request):
    """Handle password reset submission"""
    form = await request.form()
    token = form.get("token", "")
    password = form.get("password", "")
    password_confirm = form.get("password_confirm", "")

    # Re-validate token
    reset = get_password_reset_token(token)
    if not reset:
        return templates.TemplateResponse(request, "reset_password.html", {
            "error": "This reset link is invalid or has expired. Please request a new one.",
            "token": "", "valid": False
        })

    if len(password) < 8:
        return templates.TemplateResponse(request, "reset_password.html", {
            "error": "Password must be at least 8 characters.",
            "token": token, "valid": True
        })

    if password != password_confirm:
        return templates.TemplateResponse(request, "reset_password.html", {
            "error": "Passwords do not match.",
            "token": token, "valid": True
        })

    # Update the password
    import secrets as _secrets
    salt = _secrets.token_hex(16)
    hashed = hash_password(password, salt)
    update_user_password(str(reset["user_id"]), hashed, salt)
    mark_token_used(token)

    log.info("reset_password: password updated for user_id=%s", reset["user_id"])
    return RedirectResponse(url="/login?success=Password+reset+successfully.+Please+sign+in.", status_code=303)


@app.get("/create-profile", response_class=HTMLResponse)
async def create_profile_page(request: Request, error: str = None):
    """Profile creation page for new users"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse(request, "create_profile.html", {
        "error": error
    })


@app.post("/create-profile")
async def create_profile(
    request: Request,
    company_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(""),
    industry: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...)
):
    """Handle profile creation"""
    # Validate passwords match
    if password != password_confirm:
        return RedirectResponse(
            url="/create-profile?error=Passwords+do+not+match",
            status_code=302
        )

    # Validate password length
    if len(password) < 8:
        return RedirectResponse(
            url="/create-profile?error=Password+must+be+at+least+8+characters",
            status_code=302
        )

    # Check if username already exists
    if get_user_by_username(username):
        return RedirectResponse(
            url="/create-profile?error=Username+already+exists",
            status_code=302
        )

    # Create the user account
    try:
        user = register_user(username, password)
    except Exception:
        return RedirectResponse(
            url="/create-profile?error=Error+creating+account",
            status_code=302
        )

    user_id = str(user["id"])

    # Save company data for this user — keys match the rebuilt /company form.
    company_data = {
        'company_name': company_name,
        'contact_email': email,
        'contact_phone': phone,
        'industry': industry,
        'founded': '',
        'location': '',
        'focus_area': '',
        # Core Innovation
        'primary_innovation': '',
        'development_stage': '',
        'phase1_proof': '',
        # Technical Problem
        'who_suffers': '',
        'existing_solutions_fail': '',
        'core_technical_unknown': '',
        # Technical Approach
        'technical_approach': '',
        'technical_novelty': '',
        'technical_risks': '',
        # Market
        'primary_customers': '',
        'market_size': '',
        'why_now': '',
        # Team
        'team': [],
        'advisory_board': [],
        'key_partnerships': '',
    }
    save_company_context(user_id, company_data)

    # Log the user in
    request.session["user"] = {
        'username': username,
        'role': 'user',
        'created_at': datetime.now().isoformat()
    }
    request.session["username"] = username
    request.session["user_id"] = user_id
    request.session["is_admin"] = False

    # Redirect to pricing page
    return RedirectResponse(url="/pricing", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, agency: str = "nsf"):
    """Main dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    user_id = request.session.get("user_id")
    company_data = get_company_context(user_id) if user_id else {}
    company_data = company_data or {}
    agency_info = get_agency_info(agency)

    # Get proposal if exists
    proposal = app_state.proposals.get(user['username'])

    credits = get_credits(user_id) if user_id else {"pre_proposal_credits": 0, "full_proposal_credits": 0}

    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "company_data": company_data,
        "agency": agency,
        "agency_info": agency_info,
        "agencies": [
            {'code': 'nsf', 'name': 'NSF', 'icon': '🔬', 'full_name': 'National Science Foundation'},
            {'code': 'dod', 'name': 'DoD', 'icon': '🛡️', 'full_name': 'Department of Defense'},
            {'code': 'nasa', 'name': 'NASA', 'icon': '🚀', 'full_name': 'Space Technology'}
        ],
        "proposal": proposal,
        "credits": credits,
    })


@app.get("/company", response_class=HTMLResponse)
async def company_page(request: Request):
    """Company information page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    user_id = require_user(request)
    context = get_company_context(user_id) or {}

    return templates.TemplateResponse(request, "company.html", {
        "user": user,
        "company_data": context
    })


@app.post("/company")
async def save_company(
    request: Request,
    # Section 1 — Company Basics
    company_name: str = Form(""),
    founded: str = Form(""),
    location: str = Form(""),
    industry: str = Form(""),
    focus_area: str = Form(""),
    # Section 2 — Core Innovation
    primary_innovation: str = Form(""),
    development_stage: str = Form(""),
    phase1_proof: str = Form(""),
    # Section 3 — Technical Problem
    who_suffers: str = Form(""),
    existing_solutions_fail: str = Form(""),
    core_technical_unknown: str = Form(""),
    # Section 4 — Technical Approach
    technical_approach: str = Form(""),
    technical_novelty: str = Form(""),
    technical_risks: str = Form(""),
    # Section 5 — Market
    primary_customers: str = Form(""),
    market_size: str = Form(""),
    why_now: str = Form(""),
    # Section 6 — Team
    team_json: str = Form("[]"),
    advisory_board_json: str = Form("[]"),
    key_partnerships: str = Form(""),
):
    """Save company information"""
    user = get_current_user(request)
    session_user_id = request.session.get("user_id")
    log.info(
        "company_save: session_keys=%s user=%r session_user_id=%r",
        list(request.session.keys()), user, session_user_id,
    )

    if not user:
        log.warning("company_save: no user in session, redirecting to /login")
        return RedirectResponse(url="/login", status_code=302)

    user_id = require_user(request)
    log.info("company_save: resolved user_id=%r type=%s", user_id, type(user_id).__name__)

    try:
        team_data = json.loads(team_json)
    except json.JSONDecodeError:
        team_data = []

    try:
        advisory_board_data = json.loads(advisory_board_json)
    except json.JSONDecodeError:
        advisory_board_data = []

    # Load existing data to preserve unrelated fields (e.g., contact_email from signup).
    existing = get_company_context(user_id) or {}

    existing.update({
        'company_name': company_name,
        'founded': founded,
        'location': location,
        'industry': industry,
        'focus_area': focus_area,
        'primary_innovation': primary_innovation,
        'development_stage': development_stage,
        'phase1_proof': phase1_proof,
        'who_suffers': who_suffers,
        'existing_solutions_fail': existing_solutions_fail,
        'core_technical_unknown': core_technical_unknown,
        'technical_approach': technical_approach,
        'technical_novelty': technical_novelty,
        'technical_risks': technical_risks,
        'primary_customers': primary_customers,
        'market_size': market_size,
        'why_now': why_now,
        'team': team_data,
        'advisory_board': advisory_board_data,
        'key_partnerships': key_partnerships,
    })

    try:
        save_company_context(user_id, existing)
        log.info("company_save: upsert completed for user_id=%r", user_id)
        return templates.TemplateResponse(request, "partials/company_saved.html", {
            "success": True,
            "message": "Company information saved successfully!"
        })
    except Exception as exc:
        log.exception("company_save: upsert FAILED for user_id=%r: %s", user_id, exc)
        return templates.TemplateResponse(request, "partials/company_saved.html", {
            "success": False,
            "message": f"Error saving company information: {exc}"
        })


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request, agency: str = "nsf"):
    """Generate proposal page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    agency_info = get_agency_info(agency)

    return templates.TemplateResponse(request, "generate.html", {
        "user": user,
        "agency": agency,
        "agency_info": agency_info
    })


@app.get("/generate/stream")
async def generate_stream(request: Request, agency: str = "nsf"):
    """SSE endpoint for proposal generation with real-time updates"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    iterations = Config.DEFAULT_ITERATIONS
    nsf_product = request.session.get("nsf_product")
    expert_review_requested = nsf_product in ("full", "bundle")
    log.info(
        "generate_stream: user=%r agency=%s iterations=%d nsf_product=%s expert_review=%s",
        user.get("username"), agency, iterations, nsf_product, expert_review_requested,
    )

    async def event_generator():
        try:
            # Import heavy modules only when needed
            from src.cost_tracker import CostTracker
            from src.grant_agent import GrantAgent
            from src.agentic_workflow import AgenticWorkflow
            from src.quality_checker import QualityChecker
            from src.docx_exporter import DocxExporter

            start_time = time.time()

            yield f"data: {json.dumps({'type': 'status', 'message': 'Initializing system...'})}\n\n"

            # Load agency requirements
            agency_loader = load_agency_requirements(agency)

            yield f"data: {json.dumps({'type': 'status', 'message': f'Loaded {agency_loader.requirements.agency} requirements'})}\n\n"

            # Initialize components — load this user's intake from Supabase so
            # the generation prompt sees the 13-field deep-tech form data.
            cost_tracker = CostTracker()
            user_id_for_ctx = request.session.get("user_id")
            company_ctx = get_company_context(user_id_for_ctx) if user_id_for_ctx else None
            agent = GrantAgent(cost_tracker, agency_loader, company_context=company_ctx)
            workflow = AgenticWorkflow(agent, agency_loader)
            quality_checker = QualityChecker(agency_loader)
            exporter = DocxExporter()

            yield f"data: {json.dumps({'type': 'status', 'message': f'Company: {agent.company_context.company_name}'})}\n\n"

            # Get sections to generate
            ordered_sections = agency_loader.get_ordered_sections()
            required_sections = [(k, s) for k, s in ordered_sections if s.required]
            total_sections = len(required_sections)

            yield f"data: {json.dumps({'type': 'init', 'total_sections': total_sections})}\n\n"

            # Generate sections
            sections = {}
            section_count = 0

            for key, section_req in required_sections:
                section_count += 1
                progress = int((section_count / total_sections) * 100)

                # Format target length — use character limit if defined
                if section_req.max_chars > 0:
                    target_length = f"{section_req.max_chars:,} characters"
                elif section_req.min_pages == section_req.max_pages:
                    target_length = f"{section_req.min_pages} pages"
                else:
                    target_length = f"{section_req.min_pages}-{section_req.max_pages} pages"

                yield f"data: {json.dumps({'type': 'section_start', 'section': section_req.name, 'number': section_count, 'total': total_sections, 'progress': progress, 'target': target_length})}\n\n"

                # Generate section (this is blocking, but we yield updates)
                section = workflow.process_section(section_req.name, target_length, iterations)
                sections[section_req.name] = section

                current_cost = cost_tracker.get_total_cost()

                yield f"data: {json.dumps({'type': 'section_complete', 'section': section_req.name, 'word_count': section.word_count, 'cost': f'${current_cost:.2f}', 'progress': progress})}\n\n"

            # NSF only: run the seven-criteria post-generation checker.
            # Read-only — appends [REVIEWER RISK — ...] flags to the relevant
            # sections but never rewrites body content.
            if agency_loader.requirements.agency == "NSF":
                yield f"data: {json.dumps({'type': 'status', 'message': 'Running NSF seven-criteria fit check...'})}\n\n"
                ordered_names = [s_req.name for _k, s_req in agency_loader.get_ordered_sections()]
                section_list = [sections[n] for n in ordered_names if n in sections]
                checked_list = agent._check_nsf_criteria(section_list)
                sections = {s.name: s for s in checked_list}

            yield f"data: {json.dumps({'type': 'status', 'message': 'Creating proposal document...'})}\n\n"

            # Create proposal
            proposal = create_proposal_from_sections(
                company_name=agent.company_context.company_name,
                sections=sections,
                agency_loader=agency_loader
            )

            proposal.grant_type = f"{agency_loader.requirements.agency} {agency_loader.requirements.program}"
            proposal.calculate_totals()
            proposal.total_cost = cost_tracker.get_total_cost()
            proposal.generation_time_seconds = time.time() - start_time

            yield f"data: {json.dumps({'type': 'status', 'message': 'Running quality checks...'})}\n\n"

            # Quality check
            validation_results = quality_checker.validate_proposal(proposal, agent.company_context)

            yield f"data: {json.dumps({'type': 'status', 'message': 'Exporting to Word document...'})}\n\n"

            # Export
            output_file = exporter.create_document(proposal)

            # Store proposal in-memory for the /results page.
            app_state.proposals[user['username']] = {
                'proposal': proposal,
                'quality_report': validation_results,
                'output_file': output_file,
                'sections': sections,
                'generated_at': datetime.now().isoformat()
            }

            # Persist to Supabase so the SSE-status check endpoint can detect a
            # successful completion when the long-running stream's connection
            # drops on Render's free tier (10–15 min generations).
            saved_proposal_id = None
            user_id_for_save = request.session.get("user_id")
            if user_id_for_save:
                try:
                    sections_payload = {
                        name: s.model_dump() for name, s in sections.items()
                    }
                    saved = save_proposal(
                        user_id=user_id_for_save,
                        proposal_type=agency_loader.requirements.agency,
                        sections=sections_payload,
                        status="complete",
                        expert_review_requested=expert_review_requested,
                    )
                    saved_proposal_id = saved.get("id")
                    log.info("generate_stream: saved proposal id=%s for user_id=%s", saved_proposal_id, user_id_for_save)
                except Exception as save_exc:
                    log.exception("generate_stream: save_proposal failed: %s", save_exc)

            # Final result
            yield f"data: {json.dumps({'type': 'complete', 'total_words': proposal.total_word_count, 'total_cost': f'${proposal.total_cost:.2f}', 'generation_time': f'{proposal.generation_time_seconds:.1f}s', 'output_file': output_file, 'proposal_id': saved_proposal_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/check-generation-status")
async def check_generation_status(request: Request):
    """Lightweight check used by the /generate page when the SSE connection
    drops mid-stream — typical on Render's free tier for 10–15 minute jobs.
    Tells the frontend whether a proposal actually saved despite the dropped
    connection, so we can redirect to /results instead of falsely showing a
    failure."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = request.session.get("user_id")
    if not user_id:
        return {"status": "failed"}

    try:
        proposals = get_proposals_for_user(user_id)
    except Exception as exc:
        log.exception("check_generation_status: lookup failed: %s", exc)
        return {"status": "failed"}

    if not proposals:
        return {"status": "failed"}

    most_recent = proposals[0]
    created_at_raw = most_recent.get("created_at")
    if not created_at_raw:
        return {"status": "failed"}

    try:
        # Supabase returns ISO 8601; normalize trailing Z to +00:00 for fromisoformat.
        created_at = datetime.fromisoformat(str(created_at_raw).replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
    except ValueError:
        log.warning("check_generation_status: unparseable created_at=%r", created_at_raw)
        return {"status": "failed"}

    if datetime.now(timezone.utc) - created_at > timedelta(minutes=30):
        return {"status": "failed"}

    return {"status": "complete", "proposal_id": most_recent.get("id")}


def create_proposal_from_sections(company_name: str, sections: dict, agency_loader) -> GrantProposal:
    """Build a GrantProposal from the agency's ordered section definitions.

    Sections appear in the proposal in the exact order the agency's
    requirements.json defines them, with their canonical names (e.g.
    "Technology Innovation", "Market Opportunity"). Missing sections fall
    back to an empty placeholder so the proposal stays complete.
    """
    ordered = agency_loader.get_ordered_sections()
    proposal_sections: list = []
    for _key, section_req in ordered:
        section = sections.get(section_req.name)
        if section is None:
            section = GrantSection(
                name=section_req.name,
                content="[Section not generated]",
                word_count=0,
            )
        proposal_sections.append(section)

    return GrantProposal(
        company_name=company_name,
        sections=proposal_sections,
    )


@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request):
    """Results page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    proposal_data = app_state.proposals.get(user['username'])

    return templates.TemplateResponse(request, "results.html", {
        "user": user,
        "proposal_data": proposal_data
    })


@app.get("/download/{filename}")
async def download_file(request: Request, filename: str):
    """Download generated document"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    proposal_data = app_state.proposals.get(user['username'])
    if not proposal_data:
        raise HTTPException(status_code=404, detail="No proposal found")

    file_path = Path(proposal_data['output_file'])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@app.get("/api/agency/{agency}")
async def get_agency_api(request: Request, agency: str):
    """API endpoint for agency info (for HTMX)"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    agency_info = get_agency_info(agency)

    return templates.TemplateResponse(request, "partials/agency_info.html", {
        "agency": agency,
        "agency_info": agency_info
    })


# ============================================================================
# PAYMENT ROUTES
# ============================================================================

@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    """Public pricing page — marketing surface, extends marketing_base."""
    return templates.TemplateResponse(request, "pricing.html", {
        "user": get_current_user(request),
    })


def _stripe_checkout_for(request: Request, product_key: str) -> RedirectResponse:
    """Common helper: create a Stripe Checkout session for a configured product."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not Config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    cfg = Config.PRODUCTS.get(product_key)
    if not cfg:
        raise HTTPException(status_code=400, detail="Unknown product")

    price_id = getattr(Config, cfg['price_id_env'], '')
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Checkout for {product_key} is not yet available — Stripe price ID not set.",
        )

    request.session["product"] = product_key
    try:
        customer = stripe.Customer.create(metadata={'username': user['username']})
        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='payment',
            success_url=f"{Config.BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{Config.BASE_URL}/payment/cancel",
            metadata={
                'username': user['username'],
                'tier': product_key,
            },
        )
        return RedirectResponse(url=checkout_session.url, status_code=303)
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/checkout/pre-proposal")
async def checkout_pre_proposal(request: Request):
    """SBIR Phase I Pre-Proposal — $250 self-serve."""
    return _stripe_checkout_for(request, "pre_proposal")


@app.post("/checkout/full-proposal/upfront")
async def checkout_full_proposal_upfront(request: Request):
    """SBIR Phase I Full Proposal — Option A, $2,500 upfront self-serve."""
    return _stripe_checkout_for(request, "full_proposal_upfront")


@app.post("/checkout/full-proposal/success-fee")
async def checkout_full_proposal_success_fee(
    request: Request,
    invitation_letter: UploadFile = File(...),
    contact_email: str = Form(...),
    terms_accepted: str = Form(""),
):
    """SBIR Phase I Full Proposal — Option B, $0 upfront + 10% success fee.
    Captures invitation letter (Supabase Storage) and queues for Tom's review."""
    if terms_accepted != "on":
        raise HTTPException(status_code=400, detail="You must accept the success-fee terms.")

    contact = (contact_email or "").strip()
    if "@" not in contact:
        raise HTTPException(status_code=400, detail="A valid contact email is required.")

    if (invitation_letter.content_type or "").lower() != "application/pdf":
        raise HTTPException(status_code=400, detail="Invitation letter must be a PDF.")

    raw = await invitation_letter.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Invitation letter file is empty.")
    if len(raw) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Invitation letter must be under 10 MB.")

    user = get_current_user(request)
    user_id = request.session.get("user_id")

    safe_name = (invitation_letter.filename or "invitation.pdf").replace("/", "_").replace("\\", "_")
    object_path = (
        f"{user_id or 'anon'}/"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}_"
        f"{secrets.token_hex(4)}_{safe_name}"
    )

    try:
        stored_path = upload_invitation_letter(
            object_path=object_path,
            content=raw,
            content_type="application/pdf",
        )
    except StorageBucketMissingError as exc:
        log.error("success-fee upload blocked: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Option B is temporarily unavailable — invitation-letter storage is "
                "not configured. Please try again later or contact info@grantentic.us."
            ),
        )

    approval = create_pending_approval(
        user_id=user_id,
        contact_email=contact,
        product="full_proposal_success_fee",
        invitation_letter_path=stored_path,
        invitation_letter_name=safe_name,
    )

    _notify_admin_of_pending_approval(approval, contact)

    return templates.TemplateResponse(request, "full_proposal_pending.html", {
        "user": user,
        "contact_email": contact,
        "approval_id": approval["id"],
    })


def _notify_admin_of_pending_approval(approval: dict, contact_email: str) -> None:
    """Best-effort email to Tom when a new success-fee application lands."""
    if not Config.RESEND_API_KEY:
        log.warning(
            "pending_approval %s created for %s — RESEND_API_KEY not set, skipping email",
            approval["id"], contact_email,
        )
        return
    try:
        import resend
        resend.api_key = Config.RESEND_API_KEY
        resend.Emails.send({
            "from": "Grantentic <noreply@grantentic.us>",
            "to": [Config.ADMIN_NOTIFY_EMAIL],
            "subject": "New Full Proposal success-fee application",
            "html": (
                f"<p>A new SBIR Phase I Full Proposal (Option B) application is awaiting your review.</p>"
                f"<p><b>Contact:</b> {contact_email}<br>"
                f"<b>Approval ID:</b> {approval['id']}</p>"
                f"<p><a href='{Config.BASE_URL}/admin/approvals'>Open the approval queue</a></p>"
            ),
        })
        log.info("pending_approval %s: notified admin", approval["id"])
    except Exception as exc:
        log.exception("pending_approval %s: admin notification failed: %s", approval["id"], exc)


@app.get("/payment/success", response_class=HTMLResponse)
async def payment_success(request: Request, session_id: str = None):
    """Payment success page. Verifies the Stripe session and grants credits."""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    payment_verified = False
    error_message = None
    granted_product = None
    user_id = request.session.get("user_id")

    if session_id and Config.STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                payment_verified = True
                tier = (session.metadata or {}).get("tier", "")
                # Idempotency: only grant once per (user, session_id) pair.
                granted_key = f"granted_session:{session_id}"
                if user_id and tier and not request.session.get(granted_key):
                    if tier == "pre_proposal":
                        grant_credits(user_id, pre_proposal=1)
                        granted_product = "Pre-Proposal"
                    elif tier == "full_proposal_upfront":
                        grant_credits(user_id, full_proposal=1)
                        granted_product = "Full Proposal"
                    request.session[granted_key] = True
        except stripe.error.StripeError as e:
            error_message = str(e)

    return templates.TemplateResponse(request, "payment_success.html", {
        "user": user,
        "payment_verified": payment_verified,
        "error_message": error_message,
        "granted_product": granted_product,
    })


@app.get("/payment/cancel", response_class=HTMLResponse)
async def payment_cancel(request: Request):
    """Payment cancelled page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "payment_cancel.html", {
        "user": user
    })


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    if not Config.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # TODO: handle webhook events with Supabase-backed payment records
    return {"status": "success"}


@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request):
    """Billing management page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    return templates.TemplateResponse(request, "billing.html", {
        "user": user,
        "payment_status": {'can_generate': False},
    })


@app.post("/billing/portal")
async def billing_portal(request: Request):
    """Redirect to Stripe Customer Portal"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return RedirectResponse(url="/pricing", status_code=302)


@app.get("/proposals")
async def proposals_list(request: Request):
    user_id = require_user(request)
    user = get_current_user(request)
    proposals = get_proposals_for_user(user_id)
    return templates.TemplateResponse(request, "proposals.html", {"user": user, "proposals": proposals})


@app.get("/proposals/{proposal_id}")
async def proposal_detail(request: Request, proposal_id: str):
    user_id = require_user(request)
    user = get_current_user(request)
    proposal = get_proposal(proposal_id, user_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return templates.TemplateResponse(request, "proposal_detail.html", {"user": user, "proposal": proposal})


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Privacy policy page - publicly accessible"""
    user = get_current_user(request)
    return templates.TemplateResponse(request, "privacy.html", {"user": user})


# ============================================================================
# PRODUCT MARKETING PAGES (public, top-of-funnel)
# ============================================================================
# These are the /products/* stubs linked from the landing page funnel. The
# actual paid flows live at /blueprint, /register, /generate — the product
# pages are informational destinations that eventually drive there.

@app.get("/products/prompt-pack", response_class=HTMLResponse)
async def product_prompt_pack(request: Request):
    """Free SBIR Prompt Pack — email capture landing page."""
    return templates.TemplateResponse(request, "products/prompt_pack.html", {
        "user": get_current_user(request),
        "submitted_email": None,
    })


@app.post("/products/prompt-pack", response_class=HTMLResponse)
async def product_prompt_pack_signup(request: Request, email: str = Form("")):
    """Capture email for the free SBIR Prompt Pack waitlist."""
    clean = email.strip()
    if clean and "@" in clean:
        log.info("prompt_pack_signup: email=%r", clean)
    return templates.TemplateResponse(request, "products/prompt_pack.html", {
        "user": get_current_user(request),
        "submitted_email": clean if clean and "@" in clean else None,
    })


@app.get("/products/phase-i-pre-proposal", response_class=HTMLResponse)
async def product_phase_i_pre_proposal(request: Request):
    return templates.TemplateResponse(request, "products/phase_i_pre_proposal.html", {
        "user": get_current_user(request),
        "product": Config.PRODUCTS["pre_proposal"],
    })


@app.get("/products/phase-i-full-proposal", response_class=HTMLResponse)
async def product_phase_i_full_proposal(request: Request):
    return templates.TemplateResponse(request, "products/phase_i_full_proposal.html", {
        "user": get_current_user(request),
        "upfront": Config.PRODUCTS["full_proposal_upfront"],
        "success_fee": Config.PRODUCTS["full_proposal_success_fee"],
    })



# ============================================================================
# ADMIN — Full Proposal Option B approval queue
# ============================================================================

def _require_admin(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user or not request.session.get("is_admin"):
        raise HTTPException(status_code=404, detail="Not found")
    return user


@app.get("/admin/approvals", response_class=HTMLResponse)
async def admin_approvals(request: Request):
    user = _require_admin(request)
    approvals = list_pending_approvals()
    return templates.TemplateResponse(request, "admin/approvals.html", {
        "user": user,
        "approvals": approvals,
    })


@app.get("/admin/approvals/{approval_id}/letter")
async def admin_approval_letter(request: Request, approval_id: str):
    _require_admin(request)
    approval = get_pending_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    url = signed_invitation_letter_url(approval["invitation_letter_path"])
    if not url:
        raise HTTPException(
            status_code=503,
            detail="Could not generate signed URL. Bucket missing or object deleted.",
        )
    return RedirectResponse(url=url, status_code=302)


@app.post("/admin/approvals/{approval_id}/approve")
async def admin_approval_approve(request: Request, approval_id: str):
    user = _require_admin(request)
    approval = get_pending_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Already {approval['status']}")

    # Triple Redundancy Guarantee: Option B grants 3 Full Proposal credits
    # so the user has up to 3 submission cycles included.
    if approval.get("user_id"):
        grant_credits(approval["user_id"], full_proposal=3)

    decide_pending_approval(approval_id, "approved", user.get("username", "admin"))
    _email_approval_decision(approval, decision="approved")
    return RedirectResponse(url="/admin/approvals", status_code=303)


@app.post("/admin/approvals/{approval_id}/reject")
async def admin_approval_reject(request: Request, approval_id: str):
    user = _require_admin(request)
    approval = get_pending_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Already {approval['status']}")
    decide_pending_approval(approval_id, "rejected", user.get("username", "admin"))
    _email_approval_decision(approval, decision="rejected")
    return RedirectResponse(url="/admin/approvals", status_code=303)


def _email_approval_decision(approval: dict, *, decision: str) -> None:
    """Best-effort email to the applicant after Tom decides."""
    if not Config.RESEND_API_KEY:
        log.warning(
            "approval %s decided %s — RESEND_API_KEY not set, skipping applicant email",
            approval["id"], decision,
        )
        return
    try:
        import resend
        resend.api_key = Config.RESEND_API_KEY
        if decision == "approved":
            subject = "You're in — Grantentic Full Proposal (Option B) approved"
            html = (
                "<p>Your application for the SBIR Phase I Full Proposal (Success-Fee, Option B) "
                "has been approved.</p>"
                "<p>You now have access to up to <b>three Full Proposal generation cycles</b> "
                "covered by our Triple Redundancy Guarantee. "
                f"<a href='{Config.BASE_URL}/dashboard'>Sign in to start.</a></p>"
                "<p>Reminder: if NSF awards your Phase I grant, the agreed 10% success fee "
                "will be invoiced manually after the award notification.</p>"
            )
        else:
            subject = "Your Grantentic Full Proposal (Option B) application"
            html = (
                "<p>Thanks for applying to the Grantentic SBIR Phase I Full Proposal "
                "(Success-Fee, Option B) program.</p>"
                "<p>After review we are not able to accept your application for the "
                "success-only program at this time. The $2,500 upfront option (Option A) "
                f"remains available at <a href='{Config.BASE_URL}/products/phase-i-full-proposal'>"
                "grantentic.us</a> if you'd like to proceed that way.</p>"
                "<p>Questions? Reply to this email and Tom will get back to you.</p>"
            )
        resend.Emails.send({
            "from": "Grantentic <noreply@grantentic.us>",
            "to": [approval["contact_email"]],
            "subject": subject,
            "html": html,
        })
    except Exception as exc:
        log.exception("approval %s decision email failed: %s", approval["id"], exc)


# ============================================================================
# REMOVED — Blueprint product, NSF Pitch/Full/Bundle products, Accelerator
#           waitlist. Catalog collapsed to the three SBIR products above.
# ============================================================================

# SEO
@app.get("/robots.txt")
async def robots_txt():
    content = (
        "User-agent: *\n"
        "Disallow: /dashboard\n"
        "Disallow: /company\n"
        "Disallow: /generate\n"
        "Disallow: /results\n"
        "Disallow: /proposals\n"
        "Disallow: /admin\n"
        "Allow: /\n"
        "Allow: /login\n"
        "Allow: /register\n"
        "Allow: /privacy\n"
        "Allow: /pricing\n"
        "Allow: /products/prompt-pack\n"
        "Allow: /products/phase-i-pre-proposal\n"
        "Allow: /products/phase-i-full-proposal\n"
    )
    return Response(content=content, media_type="text/plain")


@app.get("/sitemap.xml")
async def sitemap_xml():
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://www.grantentic.us/</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/login</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/register</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/privacy</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/pricing</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/products/prompt-pack</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/products/phase-i-pre-proposal</loc></url>\n'
        '  <url><loc>https://www.grantentic.us/products/phase-i-full-proposal</loc></url>\n'
        '</urlset>\n'
    )
    return Response(content=content, media_type="application/xml")


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
