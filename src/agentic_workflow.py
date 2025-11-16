from rich.console import Console
from rich.panel import Panel
from src.grant_agent import GrantAgent
from src.models import GrantSection

console = Console()


class AgenticWorkflow:
    """Orchestrates the generate → critique → refine workflow"""
    
    def __init__(self, agent: GrantAgent):
        self.agent = agent
    
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
        """Generate all four sections of the grant proposal"""
        console.print("\n" + "="*70)
        console.print("[bold cyan]🚀 GRANTENTIC: AI-Powered Grant Writing System[/bold cyan]")
        console.print("[cyan]Generating NSF SBIR Phase I Proposal[/cyan]")
        console.print("="*70 + "\n")
        
        sections = {}
        
        # Define sections with target lengths
        section_specs = [
            ("Project Pitch", "1-2 pages", 1),
            ("Technical Objectives", "5-6 pages", 1),
            ("Broader Impacts", "1-2 pages", 1),
            ("Commercialization Plan", "2-3 pages", 1)
        ]
        
        for section_name, target_length, iterations in section_specs:
            sections[section_name] = self.process_section(section_name, target_length, iterations)
        
        console.print("\n" + "="*70)
        console.print("[bold green]✅ All sections generated successfully![/bold green]")
        console.print("="*70 + "\n")
        
        return sections
