import anthropic
import json
import os
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from src.models import CompanyContext, GrantSection
from src.cost_tracker import CostTracker

console = Console()


class GrantAgent:
    """AI agent for generating grant proposal sections"""
    
    def __init__(self, cost_tracker: CostTracker):
        # Configure Anthropic client for Replit AI Integrations
        api_key = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")
        
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )
        self.cost_tracker = cost_tracker
        self.model = "claude-sonnet-4-5"
        
        # Load company context
        with open("data/company_context.json", "r") as f:
            data = json.load(f)
            self.company_context = CompanyContext(**data)
        
        # Load NSF requirements
        with open("data/nsf_sbir_requirements.txt", "r") as f:
            self.nsf_requirements = f.read()
    
    def _call_claude(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> tuple[str, int, int]:
        """Call Claude API and track usage"""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        content_block = response.content[0]
        content = content_block.text if hasattr(content_block, 'text') else str(content_block)
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        
        return content, input_tokens, output_tokens
    
    def generate_section(self, section_name: str, target_length: str) -> GrantSection:
        """Generate initial draft of a grant section"""
        console.print(f"\n[bold blue]📝 Generating {section_name}...[/bold blue]")
        
        system_prompt = f"""You are an expert grant writer specializing in NSF SBIR proposals. 
You have deep knowledge of what makes successful grant applications and how to communicate complex technical concepts clearly.

Your task is to write compelling, evidence-based grant proposal sections that:
1. Clearly articulate value and innovation
2. Demonstrate technical feasibility
3. Show commercial potential
4. Follow NSF evaluation criteria
5. Are written in clear, accessible language

NSF Requirements:
{self.nsf_requirements}
"""
        
        company_json = self.company_context.model_dump_json(indent=2)
        
        section_guidelines = {
            "Project Pitch": "Write a compelling 1-2 page project pitch that clearly states the problem, solution, innovation, market opportunity, and Phase I objectives. Make it accessible to non-specialist reviewers.",
            "Technical Objectives": "Write a detailed 5-6 page technical plan covering: innovation details, current TRL level, Phase I research methodology, key technical risks and mitigation strategies, success metrics, timeline with milestones, and path to Phase II. Be specific and demonstrate deep technical expertise.",
            "Broader Impacts": "Write a 1-2 page broader impacts section covering societal benefits beyond commercialization, advancement of scientific knowledge, diversity and inclusion efforts, and ethical considerations. Show genuine commitment to positive impact.",
            "Commercialization Plan": "Write a 2-3 page commercialization plan with market analysis, target customers, competitive positioning, business model, go-to-market strategy, customer validation evidence, IP strategy, and financial projections. Demonstrate commercial viability."
        }
        
        user_prompt = f"""Generate the "{section_name}" section for an NSF SBIR Phase I grant proposal.

Target length: {target_length}

Guidelines for this section:
{section_guidelines.get(section_name, "")}

Company Information:
{company_json}

Requirements:
- Follow NSF SBIR evaluation criteria exactly
- Write in clear, professional, compelling prose
- Use specific details and evidence from the company context
- Avoid jargon and explain technical concepts clearly
- Create a strong, coherent narrative
- Focus on what will be accomplished in Phase I (6-12 months, $275K)
- Be realistic about scope and timeline

Generate the complete section now:"""
        
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task(f"Calling Claude for {section_name}...", total=None)
            content, input_tokens, output_tokens = self._call_claude(system_prompt, user_prompt, max_tokens=6000)
        
        # Track cost
        self.cost_tracker.record_usage(section_name, "generate", input_tokens, output_tokens, self.model)
        
        word_count = len(content.split())
        console.print(f"[green]✓ Generated {word_count} words[/green]")
        
        return GrantSection(
            name=section_name,
            content=content,
            word_count=word_count,
            iteration=0
        )
    
    def critique_section(self, section: GrantSection) -> str:
        """Generate critical feedback on a section"""
        console.print(f"[bold yellow]🔍 Critiquing {section.name}...[/bold yellow]")
        
        system_prompt = f"""You are a critical NSF SBIR grant reviewer with high standards.
Your job is to identify weaknesses, gaps, and areas for improvement in grant proposals.

Be constructive but thorough in identifying:
- Missing information or insufficient detail
- Weak arguments or unsupported claims
- Unclear explanations
- Misalignment with NSF criteria
- Overly ambitious or unrealistic statements
- Missing risk mitigation
- Generic or vague content

NSF Requirements:
{self.nsf_requirements}
"""
        
        user_prompt = f"""Review this grant section and provide detailed, actionable critique:

Section: {section.name}
Current draft:

{section.content}

Provide specific feedback on:
1. Alignment with NSF evaluation criteria
2. Clarity and accessibility for non-specialist reviewers
3. Strength of evidence and specificity
4. Missing information or gaps
5. Overstatements or unrealistic claims
6. Areas that need more detail or better explanation

Be thorough and constructive:"""
        
        critique, input_tokens, output_tokens = self._call_claude(system_prompt, user_prompt, max_tokens=2000)
        
        self.cost_tracker.record_usage(section.name, "critique", input_tokens, output_tokens, self.model)
        
        console.print(f"[green]✓ Critique complete[/green]")
        return critique
    
    def refine_section(self, section: GrantSection, critique: str) -> GrantSection:
        """Refine section based on critique"""
        console.print(f"[bold cyan]✨ Refining {section.name}...[/bold cyan]")
        
        system_prompt = f"""You are an expert grant writer who excels at incorporating feedback to improve proposals.
Your task is to refine grant sections based on constructive critique while maintaining the core message and evidence.

NSF Requirements:
{self.nsf_requirements}
"""
        
        user_prompt = f"""Refine this grant section based on the critique provided:

Original Section:
{section.content}

Critique:
{critique}

Instructions:
- Address all points raised in the critique
- Strengthen weak arguments with specific evidence
- Add missing information
- Improve clarity and accessibility
- Maintain appropriate scope for Phase I
- Keep the compelling narrative
- Ensure alignment with NSF criteria

Generate the improved version:"""
        
        refined_content, input_tokens, output_tokens = self._call_claude(system_prompt, user_prompt, max_tokens=6000)
        
        self.cost_tracker.record_usage(section.name, "refine", input_tokens, output_tokens, self.model)
        
        word_count = len(refined_content.split())
        console.print(f"[green]✓ Refined to {word_count} words[/green]")
        
        return GrantSection(
            name=section.name,
            content=refined_content,
            word_count=word_count,
            iteration=section.iteration + 1,
            critique=critique,
            refinement_notes="Refined based on critical feedback"
        )
