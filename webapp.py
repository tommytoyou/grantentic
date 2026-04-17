#!/usr/bin/env python3
"""
Grantentic - FastAPI Web Application
AI-Powered Grant Writing System for NSF, DoD, and NASA SBIR Phase I proposals

Full HTML control with FastAPI + Jinja2 + HTMX
"""

import json
import logging
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
    get_company_context,
    save_company_context,
    save_proposal,
    get_proposals_for_user,
    get_proposal,
)
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
app.add_middleware(
    SessionMiddleware,
    secret_key=Config.SECRET_KEY if hasattr(Config, 'SECRET_KEY') else "grantentic-secret-key-change-in-production",
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
    """Home page - redirect to login or dashboard"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


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

    # Save company data for this user
    company_data = {
        'company_name': company_name,
        'contact_email': email,
        'contact_phone': phone,
        'industry': industry,
        'founded': '',
        'location': '',
        'focus_area': '',
        'mission': '',
        'problem_statement': '',
        'solution': '',
        'team': []
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
    company_name: str = Form(""),
    founded: str = Form(""),
    location: str = Form(""),
    industry: str = Form(""),
    focus_area: str = Form(""),
    mission: str = Form(""),
    problem_statement: str = Form(""),
    solution: str = Form(""),
    team_json: str = Form("[]")
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

    # Load existing data to preserve other fields
    existing = get_company_context(user_id) or {}

    existing.update({
        'company_name': company_name,
        'founded': founded,
        'location': location,
        'industry': industry,
        'focus_area': focus_area,
        'mission': mission,
        'problem_statement': problem_statement,
        'solution': solution,
        'team': team_data
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

            # Initialize components
            cost_tracker = CostTracker()
            agent = GrantAgent(cost_tracker, agency_loader)
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
    """Create proposal from sections"""
    # Section mapping
    section_map = {
        # NSF Project Pitch sections (4 sections)
        "Technology Innovation": "project_pitch",
        "Technical Objectives and Challenges": "technical_objectives",
        "Market Opportunity": "commercialization_plan",
        "Company and Team": "biographical_sketches",
        # NSF Full Proposal sections (legacy, kept for future use)
        "Project Pitch": "project_pitch",
        "Technical Objectives": "technical_objectives",
        "Broader Impacts": "broader_impacts",
        "Commercialization Plan": "commercialization_plan",
        "Budget and Budget Justification": "budget_justification",
        "Work Plan and Timeline": "work_plan",
        "Key Personnel Biographical Sketches": "biographical_sketches",
        "Facilities, Equipment, and Other Resources": "facilities_equipment",
        # DoD sections
        "Technical Abstract": "project_pitch",
        "Identification and Significance of Problem": "broader_impacts",
        "Phase I Technical Objectives": "technical_objectives",
        "Work Plan": "work_plan",
        "Related Work": "technical_objectives",
        "Dual Use and Commercialization": "commercialization_plan",
        "Company Capabilities and Experience": "facilities_equipment",
        "Key Personnel": "biographical_sketches",
        "Cost Proposal and Budget Justification": "budget_justification",
        # NASA sections
        "Innovation and Technical Approach": "technical_objectives",
        "Anticipated Benefits": "broader_impacts",
        "Related Research": "technical_objectives",
        "Commercialization Strategy": "commercialization_plan",
        "Facilities and Equipment": "facilities_equipment",
        "Key Personnel and Qualifications": "biographical_sketches",
        "Budget Narrative and Justification": "budget_justification"
    }

    # Initialize proposal fields
    proposal_fields = {
        "company_name": company_name,
        "project_pitch": None,
        "technical_objectives": None,
        "broader_impacts": None,
        "commercialization_plan": None,
        "budget_justification": None,
        "work_plan": None,
        "biographical_sketches": None,
        "facilities_equipment": None
    }

    # Map sections
    for section_name, section in sections.items():
        field_name = section_map.get(section_name)
        if field_name:
            if proposal_fields[field_name] is None:
                proposal_fields[field_name] = section
            else:
                existing = proposal_fields[field_name]
                merged_content = f"{existing.content}\n\n{'='*50}\n\n{section.content}"
                merged_section = GrantSection(
                    name=f"{existing.name} + {section.name}",
                    content=merged_content,
                    word_count=existing.word_count + section.word_count,
                    iteration=max(existing.iteration, section.iteration)
                )
                proposal_fields[field_name] = merged_section

    # Fill missing fields
    for field_name in ["project_pitch", "technical_objectives", "broader_impacts",
                       "commercialization_plan", "budget_justification", "work_plan",
                       "biographical_sketches", "facilities_equipment"]:
        if proposal_fields[field_name] is None:
            proposal_fields[field_name] = GrantSection(
                name=f"{field_name.replace('_', ' ').title()}",
                content=f"[Section not generated for this agency]",
                word_count=0
            )

    return GrantProposal(**proposal_fields)


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


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
