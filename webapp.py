#!/usr/bin/env python3
"""
Grantentic - FastAPI Web Application
AI-Powered Grant Writing System for NSF, DoD, and NASA SBIR Phase I proposals

Full HTML control with FastAPI + Jinja2 + HTMX
"""

import json
import logging
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime
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

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

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
        "proposal": proposal
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
async def generate_stream(request: Request, agency: str = "nsf", iterations: int = 1, tier: str = "pro"):
    """SSE endpoint for proposal generation with real-time updates"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    log.info("generate_stream: user=%r agency=%s tier=%s iterations=%d", user.get("username"), agency, tier, iterations)

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

            # Store proposal
            app_state.proposals[user['username']] = {
                'proposal': proposal,
                'quality_report': validation_results,
                'output_file': output_file,
                'sections': sections,
                'generated_at': datetime.now().isoformat()
            }

            # Final result
            yield f"data: {json.dumps({'type': 'complete', 'total_words': proposal.total_word_count, 'total_cost': f'${proposal.total_cost:.2f}', 'generation_time': f'{proposal.generation_time_seconds:.1f}s', 'output_file': output_file})}\n\n"

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
    """Pricing/paywall page"""
    user = get_current_user(request)

    return templates.TemplateResponse(request, "pricing.html", {
        "user": user,
        "payment_status": {'can_generate': False},
        "tiers": Config.PAYMENT_TIERS,
        "stripe_publishable_key": Config.STRIPE_PUBLISHABLE_KEY
    })


@app.post("/checkout/one-time")
async def create_checkout_one_time(request: Request):
    """Create Stripe Checkout session for one-time purchase"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not Config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    try:
        customer = stripe.Customer.create(
            metadata={'username': user['username']}
        )

        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': Config.STRIPE_PRICE_ONE_TIME,
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{Config.BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{Config.BASE_URL}/payment/cancel",
            metadata={
                'username': user['username'],
                'tier': 'one_time'
            }
        )

        return RedirectResponse(url=checkout_session.url, status_code=303)

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/checkout/subscription/{tier}")
async def create_checkout_subscription(request: Request, tier: str):
    """Create Stripe Checkout session for subscription"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    if not Config.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    price_map = {
        'basic': Config.STRIPE_PRICE_MONTHLY_BASIC,
        'standard': Config.STRIPE_PRICE_MONTHLY_STANDARD,
        'pro': Config.STRIPE_PRICE_MONTHLY_PRO
    }

    price_id = price_map.get(tier)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid subscription tier")

    try:
        customer = stripe.Customer.create(
            metadata={'username': user['username']}
        )

        checkout_session = stripe.checkout.Session.create(
            customer=customer.id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{Config.BASE_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{Config.BASE_URL}/payment/cancel",
            metadata={
                'username': user['username'],
                'tier': f'monthly_{tier}'
            }
        )

        return RedirectResponse(url=checkout_session.url, status_code=303)

    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/payment/success", response_class=HTMLResponse)
async def payment_success(request: Request, session_id: str = None):
    """Payment success page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    payment_verified = False
    error_message = None

    if session_id and Config.STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                payment_verified = True
        except stripe.error.StripeError as e:
            error_message = str(e)

    return templates.TemplateResponse(request, "payment_success.html", {
        "user": user,
        "payment_verified": payment_verified,
        "error_message": error_message
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
        "tiers": Config.PAYMENT_TIERS
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
# BLUEPRINT PRODUCT
# ============================================================================

@app.get("/blueprint", response_class=HTMLResponse)
async def blueprint_page(request: Request):
    """SBIR Blueprint intake form"""
    return templates.TemplateResponse(request, "blueprint.html", {
        "user": get_current_user(request),
        "error": None,
        "form_data": {},
        "launch_date": Config.BLUEPRINT_LAUNCH_DATE,
    })


@app.post("/blueprint/checkout")
async def blueprint_checkout(request: Request):
    """Validate 13-field intake form and redirect to Stripe checkout"""
    form = await request.form()

    form_data = {
        # Section 1 — Problem
        "problem": form.get("problem", "").strip(),
        "who_suffers": form.get("who_suffers", "").strip(),
        "why_current_fail": form.get("why_current_fail", "").strip(),
        # Section 2 — Technical Approach
        "technology": form.get("technology", "").strip(),
        "dev_stage": form.get("dev_stage", "").strip(),
        "phase1_output": form.get("phase1_output", "").strip(),
        # Section 3 — Competitive Landscape
        "competitors": form.get("competitors", "").strip(),
        "differentiator": form.get("differentiator", "").strip(),
        "market_size": form.get("market_size", "").strip(),
        # Section 4 — Team
        "pi_background": form.get("pi_background", "").strip(),
        "team_members": form.get("team_members", "").strip(),
        "prior_work": form.get("prior_work", "").strip(),
        "solicitation": form.get("solicitation", "").strip(),
        # Meta
        "company_name": form.get("company_name", "").strip(),
        "email": form.get("email", "").strip(),
        "agency": form.get("agency", "nsf").strip(),
    }
    tier = form.get("tier", "standard")

    # Required fields
    required = ["problem", "who_suffers", "why_current_fail", "technology",
                 "dev_stage", "phase1_output", "competitors", "differentiator",
                 "pi_background", "company_name", "email"]

    if not all(form_data.get(f) for f in required):
        return templates.TemplateResponse(request, "blueprint.html", {
            "user": get_current_user(request),
            "error": "Please fill in all required fields.",
            "form_data": form_data,
            "launch_date": Config.BLUEPRINT_LAUNCH_DATE,
        })

    if "@" not in form_data["email"]:
        return templates.TemplateResponse(request, "blueprint.html", {
            "user": get_current_user(request),
            "error": "Please enter a valid email address.",
            "form_data": form_data,
            "launch_date": Config.BLUEPRINT_LAUNCH_DATE,
        })

    # Store form data in session for retrieval after payment
    request.session["blueprint_data"] = form_data

    # Select Stripe price
    if tier == "student":
        price_id = Config.STRIPE_PRICE_BLUEPRINT_STUDENT
    else:
        price_id = Config.STRIPE_PRICE_BLUEPRINT

    if not price_id or not Config.STRIPE_SECRET_KEY:
        # No Stripe configured — skip payment, go straight to generation (dev mode)
        log.warning("blueprint_checkout: no Stripe price configured, skipping payment")
        return RedirectResponse(url="/blueprint/deliver", status_code=303)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="payment",
            customer_email=form_data["email"],
            success_url=f"{Config.BASE_URL}/blueprint/deliver?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{Config.BASE_URL}/blueprint",
            metadata={
                "product": "blueprint",
                "company_name": form_data["company_name"][:500],
                "agency": form_data["agency"],
                "tier": tier,
            },
        )
        return RedirectResponse(url=checkout_session.url, status_code=303)
    except stripe.error.StripeError as e:
        log.exception("blueprint_checkout: Stripe error: %s", e)
        return templates.TemplateResponse(request, "blueprint.html", {
            "user": get_current_user(request),
            "error": f"Payment error: {e}",
            "form_data": form_data,
            "launch_date": Config.BLUEPRINT_LAUNCH_DATE,
        })


@app.get("/blueprint/deliver", response_class=HTMLResponse)
async def blueprint_deliver(request: Request, session_id: str = None):
    """After payment: generate Blueprint, email PDFs, show confirmation"""
    # Verify payment if session_id is provided
    if session_id and Config.STRIPE_SECRET_KEY:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            if session.payment_status != "paid":
                return RedirectResponse(url="/blueprint", status_code=302)
        except stripe.error.StripeError:
            return RedirectResponse(url="/blueprint", status_code=302)

    # Retrieve form data from session
    bp_data = request.session.get("blueprint_data")
    if not bp_data:
        return RedirectResponse(url="/blueprint", status_code=302)

    company_name = bp_data["company_name"]
    agency = bp_data["agency"]
    email = bp_data["email"]

    # Generate the Blueprint via Claude
    from src.blueprint import (
        generate_blueprint_content,
        create_blueprint_pdf,
        create_prompt_pack_pdf,
        send_blueprint_email,
    )

    try:
        log.info("blueprint_deliver: generating for company=%r agency=%s", company_name, agency)
        content = generate_blueprint_content(bp_data, agency)
        blueprint_pdf = create_blueprint_pdf(company_name, agency, content)
        prompt_pack_pdf = create_prompt_pack_pdf(agency)
        send_blueprint_email(email, company_name, agency, blueprint_pdf, prompt_pack_pdf)
    except Exception as exc:
        log.exception("blueprint_deliver: generation failed: %s", exc)
        return templates.TemplateResponse(request, "blueprint.html", {
            "user": get_current_user(request),
            "error": "An error occurred generating your Blueprint. Please contact info@grantentic.us for help.",
            "form_data": bp_data,
            "launch_date": Config.BLUEPRINT_LAUNCH_DATE,
        })

    # Clear blueprint data from session
    request.session.pop("blueprint_data", None)

    return templates.TemplateResponse(request, "blueprint_confirm.html", {
        "user": get_current_user(request),
        "email": email,
        "company_name": company_name,
        "agency": agency,
    })


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
        "Allow: /\n"
        "Allow: /login\n"
        "Allow: /register\n"
        "Allow: /privacy\n"
        "Allow: /blueprint\n"
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
        '  <url><loc>https://www.grantentic.us/blueprint</loc></url>\n'
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
