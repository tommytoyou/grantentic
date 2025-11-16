#!/usr/bin/env python3
"""
Grantentic - AI-Powered Grant Writing System
Generates NSF SBIR Phase I grant proposals using agentic AI workflow
"""

import time
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

from src.cost_tracker import CostTracker
from src.grant_agent import GrantAgent
from src.agentic_workflow import AgenticWorkflow
from src.quality_checker import QualityChecker
from src.docx_exporter import DocxExporter
from src.models import GrantProposal

console = Console()


def main():
    """Main entry point for Grantentic grant generation system"""
    
    # Welcome banner
    console.print("\n" + "="*70)
    console.print("[bold cyan]🚀 GRANTENTIC - AI-Powered Grant Writing System[/bold cyan]")
    console.print("[cyan]For Space Startups | NSF SBIR Phase I[/cyan]")
    console.print("="*70 + "\n")
    
    start_time = time.time()
    
    try:
        # Initialize components
        console.print("[bold]Initializing system...[/bold]")
        cost_tracker = CostTracker()
        agent = GrantAgent(cost_tracker)
        workflow = AgenticWorkflow(agent)
        quality_checker = QualityChecker()
        exporter = DocxExporter()
        
        console.print(f"[green]✓ Company: {agent.company_context.company_name}[/green]")
        console.print(f"[green]✓ Focus: {agent.company_context.focus_area}[/green]\n")
        
        # Generate all sections using agentic workflow
        sections = workflow.generate_full_proposal()
        
        # Create proposal object
        proposal = GrantProposal(
            company_name=agent.company_context.company_name,
            project_pitch=sections["Project Pitch"],
            technical_objectives=sections["Technical Objectives"],
            broader_impacts=sections["Broader Impacts"],
            commercialization_plan=sections["Commercialization Plan"]
        )
        
        # Calculate totals
        proposal.calculate_totals()
        proposal.total_cost = cost_tracker.get_total_cost()
        proposal.generation_time_seconds = time.time() - start_time
        
        # Quality validation
        validation_results = quality_checker.validate_proposal(proposal)
        
        # Export to Word document
        output_file = exporter.create_document(proposal)
        
        # Cost summary
        cost_tracker.print_summary()
        
        # Final summary
        console.print("\n" + "="*70)
        console.print(Panel.fit(
            f"[bold green]✅ Grant Generation Complete![/bold green]\n\n"
            f"📄 Output: {output_file}\n"
            f"📊 Total Words: {proposal.total_word_count:,}\n"
            f"💰 Total Cost: ${proposal.total_cost:.2f}\n"
            f"⏱️  Generation Time: {proposal.generation_time_seconds:.1f}s\n"
            f"✓ Quality: {'Passed all checks' if validation_results['overall_passed'] else 'Review recommended'}",
            border_style="green"
        ))
        console.print("="*70 + "\n")
        
        # Cost target check
        if proposal.total_cost <= 5.0:
            console.print(f"[bold green]🎯 Success! Cost ${proposal.total_cost:.2f} is within target ($2-5)[/bold green]\n")
        else:
            console.print(f"[bold yellow]⚠️  Cost ${proposal.total_cost:.2f} exceeds target of $5.00[/bold yellow]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {str(e)}[/bold red]\n")
        raise


if __name__ == "__main__":
    main()
