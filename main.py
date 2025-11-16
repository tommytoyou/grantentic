#!/usr/bin/env python3
"""
Grantentic - AI-Powered Grant Writing System
Generates grant proposals for multiple funding agencies (NSF, DoD, NASA)
"""

import time
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

from config import Config
from src.cost_tracker import CostTracker
from src.grant_agent import GrantAgent
from src.agentic_workflow import AgenticWorkflow
from src.quality_checker import QualityChecker
from src.docx_exporter import DocxExporter
from src.agency_loader import load_agency_requirements
from src.models import GrantProposal

console = Console()


def create_proposal_from_sections(company_name: str, sections: dict, agency_loader) -> GrantProposal:
    """
    Dynamically create proposal object based on agency sections

    Different agencies have different section requirements, so we need to
    map them to the GrantProposal model fields
    """
    # Map agency section names to GrantProposal field names
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
        "Technical Abstract": "project_pitch",  # Map to project_pitch
        "Identification and Significance of Problem": "broader_impacts",  # Map to broader_impacts
        "Phase I Technical Objectives": "technical_objectives",
        "Work Plan": "work_plan",
        "Related Work": "technical_objectives",  # Append to technical objectives
        "Dual Use and Commercialization": "commercialization_plan",
        "Company Capabilities and Experience": "facilities_equipment",
        "Key Personnel": "biographical_sketches",
        "Cost Proposal and Budget Justification": "budget_justification",

        # NASA sections
        "Innovation and Technical Approach": "technical_objectives",
        "Anticipated Benefits": "broader_impacts",
        "Related Research": "technical_objectives",  # Append to technical objectives
        "Commercialization Strategy": "commercialization_plan",
        "Facilities and Equipment": "facilities_equipment",
        "Key Personnel and Qualifications": "biographical_sketches",
        "Budget Narrative and Justification": "budget_justification"
    }

    # Initialize all fields with empty sections
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

    # Map generated sections to proposal fields
    for section_name, section in sections.items():
        field_name = section_map.get(section_name)
        if field_name:
            if proposal_fields[field_name] is None:
                proposal_fields[field_name] = section
            else:
                # If field already has content, merge (for sections that map to same field)
                existing = proposal_fields[field_name]
                merged_content = f"{existing.content}\n\n{'='*50}\n\n{section.content}"
                merged_section = GrantSection(
                    name=f"{existing.name} + {section.name}",
                    content=merged_content,
                    word_count=existing.word_count + section.word_count,
                    iteration=max(existing.iteration, section.iteration)
                )
                proposal_fields[field_name] = merged_section

    # Fill in any missing required fields with placeholder sections
    from src.models import GrantSection
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


def main():
    """Main entry point for Grantentic grant generation system"""

    # Welcome banner
    console.print("\n" + "="*70)
    console.print("[bold cyan]🚀 GRANTENTIC - AI-Powered Grant Writing System[/bold cyan]")
    console.print("[cyan]Multi-Agency Support: NSF | DoD | NASA[/cyan]")
    console.print("="*70 + "\n")

    start_time = time.time()

    try:
        # Display and validate agency selection
        Config.print_agency_info()

        if not Config.validate_agency():
            console.print(f"[bold red]❌ Error: Invalid agency '{Config.AGENCY}'[/bold red]")
            console.print(f"[yellow]Available agencies: {', '.join(Config.list_available_agencies())}[/yellow]")
            console.print(f"\n[cyan]To change agency, set GRANT_AGENCY environment variable:[/cyan]")
            console.print(f"[cyan]  export GRANT_AGENCY=nsf  # or dod, nasa[/cyan]\n")
            return

        # Initialize components
        console.print("[bold]Initializing system...[/bold]")

        # Load agency requirements
        agency_loader = load_agency_requirements(Config.AGENCY, Config.AGENCY_TEMPLATES_DIR)
        agency_loader.print_summary()

        # Initialize components with agency loader
        cost_tracker = CostTracker()
        agent = GrantAgent(cost_tracker, agency_loader)
        workflow = AgenticWorkflow(agent, agency_loader)
        quality_checker = QualityChecker(agency_loader)
        exporter = DocxExporter()

        console.print(f"[green]✓ Company: {agent.company_context.company_name}[/green]")
        console.print(f"[green]✓ Focus: {agent.company_context.focus_area}[/green]\n")

        # Generate all sections using agentic workflow
        sections = workflow.generate_full_proposal()

        # Create proposal object dynamically based on agency
        proposal = create_proposal_from_sections(
            company_name=agent.company_context.company_name,
            sections=sections,
            agency_loader=agency_loader
        )

        # Set agency-specific grant type
        proposal.grant_type = f"{agency_loader.requirements.agency} {agency_loader.requirements.program}"

        # Calculate totals
        proposal.calculate_totals()
        proposal.total_cost = cost_tracker.get_total_cost()
        proposal.generation_time_seconds = time.time() - start_time

        # Quality validation with enhanced checking
        validation_results = quality_checker.validate_proposal(proposal, agent.company_context)

        # Save quality report to file
        output_dir = Path(Config.OUTPUT_DIR)
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        agency_prefix = Config.AGENCY.upper()
        report_filename = f"{agent.company_context.company_name.replace(' ', '_')}_{agency_prefix}_Quality_Report_{timestamp}.md"
        report_filepath = output_dir / report_filename

        with open(report_filepath, 'w') as f:
            f.write(validation_results['report'])

        console.print(f"[cyan]📋 Quality report saved to: {report_filepath}[/cyan]")

        # Export to Word document
        output_file = exporter.create_document(proposal)

        # Cost summary
        cost_tracker.print_summary()

        # Final summary
        console.print("\n" + "="*70)

        trimmed_info = ""
        if validation_results.get('trimmed_sections'):
            trimmed_count = len(validation_results['trimmed_sections'])
            trimmed_info = f"\n✂️  Auto-trimmed: {trimmed_count} section(s)"

        suggestions_info = ""
        if validation_results.get('suggestions_count', 0) > 0:
            suggestions_info = f"\n💡 Suggestions: {validation_results['suggestions_count']} improvement(s) recommended"

        console.print(Panel.fit(
            f"[bold green]✅ Grant Generation Complete![/bold green]\n\n"
            f"🏛️  Agency: {agency_loader.requirements.agency} {agency_loader.requirements.program}\n"
            f"💰 Funding: ${agency_loader.get_funding_amount():,}\n"
            f"📄 Proposal: {output_file}\n"
            f"📋 Quality Report: {report_filepath}\n"
            f"📊 Total Words: {proposal.total_word_count:,}\n"
            f"💵 Generation Cost: ${proposal.total_cost:.2f}\n"
            f"⏱️  Generation Time: {proposal.generation_time_seconds:.1f}s{trimmed_info}{suggestions_info}",
            border_style="green"
        ))
        console.print("="*70 + "\n")

        # Cost target check
        if proposal.total_cost <= Config.TARGET_COST_MAX:
            console.print(f"[bold green]🎯 Success! Cost ${proposal.total_cost:.2f} is within target (${Config.TARGET_COST_MIN}-${Config.TARGET_COST_MAX})[/bold green]\n")
        else:
            console.print(f"[bold yellow]⚠️  Cost ${proposal.total_cost:.2f} exceeds target of ${Config.TARGET_COST_MAX:.2f}[/bold yellow]\n")

    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")
        raise


if __name__ == "__main__":
    main()
