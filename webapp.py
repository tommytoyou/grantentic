#!/usr/bin/env python3
"""
Grantentic - FastAPI Web Application
AI-Powered Grant Writing System for NSF, DoD, and NASA SBIR Phase I proposals

Full HTML control with FastAPI + Jinja2 + HTMX
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Form, Depends, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from config import Config
from src.auth import authenticate_user, initialize_admin_account
from src.agency_loader import load_agency_requirements
from src.models import GrantProposal, GrantSection


# Application state
class AppState:
    proposals: Dict[str, Any] = {}
    generation_tasks: Dict[str, Any] = {}


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize on startup"""
    initialize_admin_account()
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


# Helper functions
def load_company_data() -> Dict[str, Any]:
    """Load company data from JSON file"""
    try:
        with open('data/company_context.json', 'r') as f:
            return json.load(f)
    except Exception:
        return {
            'company_name': '',
            'founded': '',
            'location': '',
            'industry': '',
            'focus_area': '',
            'mission': '',
            'problem_statement': '',
            'solution': '',
            'team': []
        }


def save_company_data(data: Dict[str, Any]) -> bool:
    """Save company data to JSON file"""
    try:
        Path('data').mkdir(exist_ok=True)
        with open('data/company_context.json', 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


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
async def login_page(request: Request, error: str = None):
    """Login page"""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error
    })


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Handle login"""
    user = authenticate_user(username, password)
    if user:
        request.session["user"] = user
        return RedirectResponse(url="/dashboard", status_code=302)

    return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, agency: str = "nsf"):
    """Main dashboard"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    company_data = load_company_data()
    agency_info = get_agency_info(agency)

    # Get proposal if exists
    proposal = app_state.proposals.get(user['username'])

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
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

    company_data = load_company_data()

    return templates.TemplateResponse("company.html", {
        "request": request,
        "user": user,
        "company_data": company_data
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
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    try:
        team_data = json.loads(team_json)
    except json.JSONDecodeError:
        team_data = []

    # Load existing data to preserve other fields
    existing = load_company_data()

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

    if save_company_data(existing):
        return templates.TemplateResponse("partials/company_saved.html", {
            "request": request,
            "success": True,
            "message": "Company information saved successfully!"
        })
    else:
        return templates.TemplateResponse("partials/company_saved.html", {
            "request": request,
            "success": False,
            "message": "Error saving company information"
        })


@app.get("/generate", response_class=HTMLResponse)
async def generate_page(request: Request, agency: str = "nsf"):
    """Generate proposal page"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)

    agency_info = get_agency_info(agency)

    return templates.TemplateResponse("generate.html", {
        "request": request,
        "user": user,
        "agency": agency,
        "agency_info": agency_info
    })


@app.get("/generate/stream")
async def generate_stream(request: Request, agency: str = "nsf", iterations: int = 1):
    """SSE endpoint for proposal generation with real-time updates"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

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

                # Format target length
                if section_req.min_pages == section_req.max_pages:
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
        # NSF sections
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

    return templates.TemplateResponse("results.html", {
        "request": request,
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

    return templates.TemplateResponse("partials/agency_info.html", {
        "request": request,
        "agency": agency,
        "agency_info": agency_info
    })


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
