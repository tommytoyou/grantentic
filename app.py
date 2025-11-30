#!/usr/bin/env python3
"""
Grantentic - Streamlit Web Application
AI-Powered Grant Writing System for NSF, DoD, and NASA SBIR Phase I proposals

OPTIMIZED FOR FAST HEALTH CHECKS - All heavy imports are deferred
"""

import streamlit as st

# Configure page FIRST - this is the only thing that runs immediately
st.set_page_config(
    page_title="Grantentic - AI Grant Writer",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state ONLY (no imports, no file I/O)
if 'app_initialized' not in st.session_state:
    st.session_state.app_initialized = False
if 'company_data' not in st.session_state:
    st.session_state.company_data = None
if 'generated_proposal' not in st.session_state:
    st.session_state.generated_proposal = None
if 'quality_report' not in st.session_state:
    st.session_state.quality_report = None
if 'generation_in_progress' not in st.session_state:
    st.session_state.generation_in_progress = False
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False


def get_lazy_imports():
    """Import all modules lazily when needed - returns dict of imported modules"""
    import json
    import time
    from pathlib import Path
    from datetime import datetime
    import io
    import traceback
    import sys

    from config import Config
    from src.cost_tracker import CostTracker
    from src.grant_agent import GrantAgent
    from src.agentic_workflow import AgenticWorkflow
    from src.quality_checker import QualityChecker
    from src.docx_exporter import DocxExporter
    from src.agency_loader import load_agency_requirements
    from src.models import GrantProposal, CompanyContext, GrantSection

    return {
        'json': json,
        'time': time,
        'Path': Path,
        'datetime': datetime,
        'io': io,
        'traceback': traceback,
        'sys': sys,
        'Config': Config,
        'CostTracker': CostTracker,
        'GrantAgent': GrantAgent,
        'AgenticWorkflow': AgenticWorkflow,
        'QualityChecker': QualityChecker,
        'DocxExporter': DocxExporter,
        'load_agency_requirements': load_agency_requirements,
        'GrantProposal': GrantProposal,
        'CompanyContext': CompanyContext,
        'GrantSection': GrantSection
    }


def load_company_data():
    """Lazy load company data only when needed"""
    if not st.session_state.data_loaded:
        try:
            imports = get_lazy_imports()
            json = imports['json']

            with open('data/company_context.json', 'r') as f:
                st.session_state.company_data = json.load(f)
            st.session_state.data_loaded = True
        except Exception as e:
            st.error(f"Error loading company data: {e}")
            st.session_state.company_data = {
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
            st.session_state.data_loaded = True


def create_proposal_from_sections(company_name: str, sections: dict, agency_loader):
    """Create proposal from sections"""
    imports = get_lazy_imports()
    GrantProposal = imports['GrantProposal']
    GrantSection = imports['GrantSection']

    # Section mapping (same as main.py)
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


def render_sidebar():
    """Render sidebar with agency selector and settings"""
    imports = get_lazy_imports()
    load_agency_requirements = imports['load_agency_requirements']

    with st.sidebar:
        st.title("🚀 Grantentic")
        st.caption("AI-Powered Grant Writing System")

        st.divider()

        # Agency selector
        st.subheader("🏛️ Select Funding Agency")

        agency = st.selectbox(
            "Choose agency:",
            options=['nsf', 'dod', 'nasa'],
            format_func=lambda x: {
                'nsf': '🔬 NSF - National Science Foundation',
                'dod': '🛡️ DoD - Department of Defense',
                'nasa': '🚀 NASA - Space Technology'
            }[x],
            help="Select the target funding agency for your proposal"
        )

        # Load and display agency info
        try:
            agency_loader = load_agency_requirements(agency)
            agency_info = agency_loader.requirements

            st.info(f"""
            **Program:** {agency_info.program}
            **Funding:** ${agency_info.funding_amount:,}
            **Duration:** {agency_info.duration_months} months
            **Sections:** {len(agency_info.sections)} required
            """)

        except Exception as e:
            st.error(f"Error loading agency: {e}")
            agency_loader = None

        st.divider()

        # Settings
        st.subheader("⚙️ Settings")

        iterations = st.number_input(
            "Critique-Refine Iterations",
            min_value=0,
            max_value=3,
            value=1,
            help="Number of times to critique and refine each section (increases quality but also cost)"
        )

        auto_trim = st.checkbox(
            "Auto-trim long sections",
            value=True,
            help="Automatically trim sections that exceed page limits"
        )

        st.divider()

        # Quick stats
        if st.session_state.generated_proposal:
            st.subheader("📊 Current Proposal")
            prop = st.session_state.generated_proposal
            st.metric("Total Words", f"{prop.total_word_count:,}")
            st.metric("Generation Cost", f"${prop.total_cost:.2f}")
            st.metric("Generation Time", f"{prop.generation_time_seconds:.1f}s")

        return agency, agency_loader, iterations, auto_trim


def render_company_editor():
    """Render company data editor form"""
    imports = get_lazy_imports()
    json = imports['json']

    # Ensure company data is loaded
    if not st.session_state.data_loaded:
        load_company_data()

    st.header("📝 Company Information")
    st.caption("Edit your company details for the grant proposal")

    with st.form("company_form"):
        col1, col2 = st.columns(2)

        with col1:
            company_name = st.text_input(
                "Company Name",
                value=st.session_state.company_data.get('company_name', ''),
                help="Official company name"
            )

            founded = st.text_input(
                "Founded Year",
                value=st.session_state.company_data.get('founded', ''),
                help="Year company was founded"
            )

            location = st.text_input(
                "Location",
                value=st.session_state.company_data.get('location', ''),
                help="City and state"
            )

            industry = st.text_input(
                "Industry",
                value=st.session_state.company_data.get('industry', ''),
                help="Primary industry"
            )

        with col2:
            focus_area = st.text_area(
                "Focus Area",
                value=st.session_state.company_data.get('focus_area', ''),
                height=100,
                help="Brief description of company focus"
            )

            mission = st.text_area(
                "Mission Statement",
                value=st.session_state.company_data.get('mission', ''),
                height=100,
                help="Company mission statement"
            )

        st.subheader("💡 Technology & Innovation")

        col1, col2 = st.columns(2)

        with col1:
            problem_statement = st.text_area(
                "Problem Statement",
                value=st.session_state.company_data.get('problem_statement', ''),
                height=150,
                help="What problem are you solving?"
            )

        with col2:
            solution = st.text_area(
                "Solution",
                value=st.session_state.company_data.get('solution', ''),
                height=150,
                help="How does your technology solve this problem?"
            )

        st.subheader("👥 Team Members")
        st.caption("Key personnel (edit the JSON for more control)")

        # Display team in expandable section
        with st.expander("View/Edit Team"):
            team_json = st.text_area(
                "Team (JSON format)",
                value=json.dumps(st.session_state.company_data.get('team', []), indent=2),
                height=200,
                help="Edit team members in JSON format"
            )

        # Form submit button
        submitted = st.form_submit_button("💾 Save Company Information", use_container_width=True)

        if submitted:
            try:
                # Parse team JSON
                team_data = json.loads(team_json)

                # Update session state
                st.session_state.company_data.update({
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

                # Save to file
                with open('data/company_context.json', 'w') as f:
                    json.dump(st.session_state.company_data, f, indent=2)

                st.success("✅ Company information saved successfully!")

            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON in team data: {e}")
            except Exception as e:
                st.error(f"❌ Error saving company data: {e}")


def generate_proposal(agency, agency_loader, iterations):
    """Generate grant proposal with real-time progress updates"""
    imports = get_lazy_imports()
    time = imports['time']
    traceback = imports['traceback']
    CostTracker = imports['CostTracker']
    GrantAgent = imports['GrantAgent']
    AgenticWorkflow = imports['AgenticWorkflow']
    QualityChecker = imports['QualityChecker']
    DocxExporter = imports['DocxExporter']

    # Progress containers
    progress_container = st.container()
    status_container = st.container()

    with progress_container:
        overall_progress = st.progress(0)
        current_section_text = st.empty()
        cost_text = st.empty()

    try:
        start_time = time.time()

        # Initialize components
        with status_container:
            with st.status("🔧 Initializing system...", expanded=True) as status:
                st.write("Loading agency requirements...")

                cost_tracker = CostTracker()
                agent = GrantAgent(cost_tracker, agency_loader)
                workflow = AgenticWorkflow(agent, agency_loader)
                quality_checker = QualityChecker(agency_loader)
                exporter = DocxExporter()

                st.write(f"✓ Agency: {agency_loader.requirements.agency}")
                st.write(f"✓ Company: {agent.company_context.company_name}")
                st.write(f"✓ Sections to generate: {len(agency_loader.get_ordered_sections())}")

                status.update(label="✅ System initialized", state="complete")

        # Get sections to generate
        ordered_sections = agency_loader.get_ordered_sections()
        total_sections = len([s for k, s in ordered_sections if s.required])

        # Generate sections
        sections = {}
        section_count = 0

        with status_container:
            with st.status("📝 Generating proposal sections...", expanded=True) as status:
                for key, section_req in ordered_sections:
                    if not section_req.required:
                        continue

                    section_count += 1

                    # Update progress
                    progress = section_count / total_sections
                    overall_progress.progress(progress)
                    current_section_text.markdown(
                        f"**Section {section_count}/{total_sections}:** {section_req.name}"
                    )

                    # Format target length
                    if section_req.min_pages == section_req.max_pages:
                        target_length = f"{section_req.min_pages} pages"
                    else:
                        target_length = f"{section_req.min_pages}-{section_req.max_pages} pages"

                    st.write(f"🔄 Generating: {section_req.name} ({target_length})...")

                    # Generate section
                    section = workflow.process_section(section_req.name, target_length, iterations)
                    sections[section_req.name] = section

                    # Update cost
                    current_cost = cost_tracker.get_total_cost()
                    cost_text.markdown(f"**Current Cost:** ${current_cost:.2f}")

                    st.write(f"✓ Completed: {section.word_count} words")

                status.update(label="✅ All sections generated", state="complete")

        # Create proposal
        with status_container:
            with st.status("🔍 Running quality checks...", expanded=True) as status:
                proposal = create_proposal_from_sections(
                    company_name=agent.company_context.company_name,
                    sections=sections,
                    agency_loader=agency_loader
                )

                proposal.grant_type = f"{agency_loader.requirements.agency} {agency_loader.requirements.program}"
                proposal.calculate_totals()
                proposal.total_cost = cost_tracker.get_total_cost()
                proposal.generation_time_seconds = time.time() - start_time

                st.write("Running quality validation...")
                validation_results = quality_checker.validate_proposal(proposal, agent.company_context)

                st.write(f"✓ Quality score: {100 - validation_results.get('suggestions_count', 0) * 5:.0f}%")

                status.update(label="✅ Quality checks complete", state="complete")

        # Export document
        with status_container:
            with st.status("📄 Creating Word document...", expanded=True) as status:
                output_file = exporter.create_document(proposal)
                st.write(f"✓ Document saved: {output_file}")
                status.update(label="✅ Document created", state="complete")

        # Save to session state
        st.session_state.generated_proposal = proposal
        st.session_state.quality_report = validation_results
        st.session_state.output_file = output_file
        st.session_state.sections = sections

        # Final progress
        overall_progress.progress(1.0)
        current_section_text.markdown("**✅ Generation Complete!**")
        cost_text.markdown(f"**Final Cost:** ${proposal.total_cost:.2f}")

        return True

    except Exception as e:
        st.error(f"❌ Error during generation: {str(e)}")
        st.code(traceback.format_exc())
        return False


def render_results():
    """Render proposal results with tabs and download button"""
    if not st.session_state.generated_proposal:
        st.info("👆 Generate a proposal to see results here")
        return

    imports = get_lazy_imports()
    Path = imports['Path']
    datetime = imports['datetime']

    prop = st.session_state.generated_proposal

    st.header("📊 Generated Proposal")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Words", f"{prop.total_word_count:,}")

    with col2:
        st.metric("Generation Cost", f"${prop.total_cost:.2f}")

    with col3:
        st.metric("Generation Time", f"{prop.generation_time_seconds:.1f}s")

    with col4:
        suggestions = st.session_state.quality_report.get('suggestions_count', 0)
        quality_score = max(0, 100 - suggestions * 5)
        st.metric("Quality Score", f"{quality_score}%")

    st.divider()

    # Download button
    if st.session_state.output_file and Path(st.session_state.output_file).exists():
        with open(st.session_state.output_file, 'rb') as f:
            st.download_button(
                label="📥 Download Word Document",
                data=f.read(),
                file_name=Path(st.session_state.output_file).name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )

    st.divider()

    # Tabs for sections and quality report
    tab1, tab2 = st.tabs(["📄 Proposal Sections", "🔍 Quality Report"])

    with tab1:
        # Display all sections in expandable containers
        sections_to_display = [
            ("Project Pitch", prop.project_pitch),
            ("Technical Objectives", prop.technical_objectives),
            ("Broader Impacts", prop.broader_impacts),
            ("Commercialization Plan", prop.commercialization_plan),
            ("Budget & Justification", prop.budget_justification),
            ("Work Plan & Timeline", prop.work_plan),
            ("Biographical Sketches", prop.biographical_sketches),
            ("Facilities & Equipment", prop.facilities_equipment)
        ]

        for section_name, section in sections_to_display:
            if section and section.word_count > 0:
                with st.expander(f"**{section_name}** ({section.word_count} words)", expanded=False):
                    st.markdown(section.content)

                    # Section metrics
                    col1, col2 = st.columns(2)
                    with col1:
                        st.caption(f"Word count: {section.word_count}")
                    with col2:
                        st.caption(f"Iteration: {section.iteration}")

    with tab2:
        # Display quality report
        if st.session_state.quality_report:
            report = st.session_state.quality_report.get('report', 'No report available')
            st.markdown(report)

            # Download quality report
            st.download_button(
                label="📥 Download Quality Report (Markdown)",
                data=report,
                file_name=f"quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )


def main():
    """Main application - optimized for fast initial load"""

    # Render minimal page first for fast health checks
    st.title("🚀 Grantentic - AI-Powered Grant Writing")
    st.caption("Generate professional SBIR Phase I proposals for NSF, DoD, and NASA")

    # Mark app as initialized after first render
    if not st.session_state.app_initialized:
        st.session_state.app_initialized = True

    try:
        # Render sidebar - this loads agency data
        agency, agency_loader, iterations, auto_trim = render_sidebar()

        # Load company data lazily
        if not st.session_state.data_loaded:
            load_company_data()

    except Exception as e:
        st.error(f"Error initializing application: {e}")
        st.write("Please refresh the page or contact support if the issue persists.")
        return

    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["🏢 Company Info", "✨ Generate Proposal", "📊 Results"])

    with tab1:
        render_company_editor()

    with tab2:
        st.header("✨ Generate Grant Proposal")

        if agency_loader:
            st.info(f"""
            **Selected Agency:** {agency_loader.requirements.agency}
            **Program:** {agency_loader.requirements.program}
            **Funding Amount:** ${agency_loader.requirements.funding_amount:,}
            **Duration:** {agency_loader.requirements.duration_months} months
            """)

            st.warning("⚠️ **Note:** Proposal generation may take 2-5 minutes and will cost approximately $2-5 in API fees.")

            # Generate button
            if st.button("🚀 Generate Grant Proposal", type="primary", use_container_width=True):
                if not st.session_state.generation_in_progress:
                    st.session_state.generation_in_progress = True
                    success = generate_proposal(agency, agency_loader, iterations)
                    st.session_state.generation_in_progress = False

                    if success:
                        st.success("✅ Proposal generated successfully! Check the Results tab.")
                        st.balloons()
                else:
                    st.warning("⏳ Generation already in progress...")
        else:
            st.error("❌ Please select a valid agency in the sidebar")

    with tab3:
        render_results()


if __name__ == "__main__":
    main()
