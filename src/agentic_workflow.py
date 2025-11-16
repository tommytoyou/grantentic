from rich.console import Console
from rich.panel import Panel
from src.grant_agent import GrantAgent
from src.models import GrantSection
from src.agency_loader import AgencyLoader

console = Console()


class AgenticWorkflow:
    """Orchestrates the generate → critique → refine workflow"""

    def __init__(self, agent: GrantAgent, agency_loader: AgencyLoader):
        self.agent = agent
        self.agency_loader = agency_loader
    
    def process_section(self, section_name: str, target_length: str, iterations: int = 1) -> GrantSection:
        """
        Execute agentic workflow for a section:
        1. Generate initial draft
        2. Self-critique
        3. Refine based on critique
        
        Args:
            section_name: Name of the section to generate
            target_length: Target length description (e.g., "1-2 pages")
            iterations: Number of critique-refine cycles (default 1)
        """
        console.print(Panel.fit(
            f"[bold]Starting Agentic Workflow: {section_name}[/bold]\n"
            f"Target: {target_length} | Iterations: {iterations}",
            border_style="blue"
        ))
        
        # Step 1: Generate initial draft
        current_section = self.agent.generate_section(section_name, target_length)
        
        # Step 2-3: Critique and refine (iterate)
        for i in range(iterations):
            console.print(f"\n[bold magenta]🔄 Iteration {i + 1}/{iterations}[/bold magenta]")
            
            # Generate critique
            critique = self.agent.critique_section(current_section)
            
            # Display critique preview
            critique_preview = critique[:300] + "..." if len(critique) > 300 else critique
            console.print(Panel(
                f"[yellow]{critique_preview}[/yellow]",
                title="Critique Preview",
                border_style="yellow"
            ))
            
            # Refine based on critique
            current_section = self.agent.refine_section(current_section, critique)
        
        console.print(f"\n[bold green]✅ {section_name} complete after {iterations} iteration(s)[/bold green]")
        return current_section
    
    def generate_full_proposal(self) -> dict:
        """Generate all sections of the grant proposal based on agency requirements"""
        agency_info = self.agency_loader.requirements

        console.print("\n" + "="*70)
        console.print("[bold cyan]🚀 GRANTENTIC: AI-Powered Grant Writing System[/bold cyan]")
        console.print(f"[cyan]Generating {agency_info.agency} {agency_info.program} Proposal[/cyan]")
        console.print("="*70 + "\n")

        sections = {}

        # Build section specs from agency requirements
        section_specs = []
        for key, section_req in self.agency_loader.get_ordered_sections():
            if section_req.required:
                # Format target length
                if section_req.min_pages == section_req.max_pages:
                    target_length = f"{section_req.min_pages} pages"
                else:
                    target_length = f"{section_req.min_pages}-{section_req.max_pages} pages"

                section_specs.append((section_req.name, target_length, 1))

        console.print(f"[yellow]📋 Generating {len(section_specs)} required sections[/yellow]\n")

        for section_name, target_length, iterations in section_specs:
            sections[section_name] = self.process_section(section_name, target_length, iterations)

        console.print("\n" + "="*70)
        console.print("[bold green]✅ All sections generated successfully![/bold green]")
        console.print("="*70 + "\n")

        return sections
