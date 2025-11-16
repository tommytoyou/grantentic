"""
Agency Requirements Loader
Loads agency-specific requirements, page limits, and evaluation criteria
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from rich.console import Console

console = Console()


class SectionRequirements(BaseModel):
    """Requirements for a single proposal section"""
    name: str
    required: bool
    min_pages: float
    max_pages: float
    min_words: int
    max_words: int
    order: int
    guidelines: str
    required_keywords: list[str]
    description: str


class EvaluationCriterion(BaseModel):
    """Evaluation criterion with weight and description"""
    weight: float
    description: str
    sub_criteria: list[str]


class FormatSpecifications(BaseModel):
    """Document format specifications"""
    font: str
    font_size: int
    line_spacing: float
    margins: Dict[str, float]
    page_numbers: bool
    headers_footers: bool
    words_per_page: int
    references_format: str
    volume_limit: Optional[str] = None


class AgencyRequirements(BaseModel):
    """Complete agency requirements specification"""
    agency: str
    program: str
    funding_amount: int
    duration_months: int
    description: str
    sections: Dict[str, SectionRequirements]
    evaluation_criteria: Dict[str, EvaluationCriterion]
    format_specifications: FormatSpecifications
    special_requirements: Dict[str, Any]
    submission_requirements: Dict[str, str]


class AgencyLoader:
    """Loads and manages agency-specific requirements"""

    def __init__(self, agency: str, templates_dir: str = "agency_templates"):
        self.agency = agency.lower()
        self.templates_dir = Path(templates_dir)
        self.requirements: Optional[AgencyRequirements] = None
        self._load_requirements()

    def _load_requirements(self):
        """Load requirements from JSON file"""
        # Map agency to directory
        agency_map = {
            'nsf': 'nsf',
            'dod': 'dod',
            'nasa': 'nasa'
        }

        if self.agency not in agency_map:
            raise ValueError(f"Unknown agency: {self.agency}. Supported: {list(agency_map.keys())}")

        # Construct path to requirements file
        requirements_file = self.templates_dir / agency_map[self.agency] / 'requirements.json'

        if not requirements_file.exists():
            raise FileNotFoundError(f"Requirements file not found: {requirements_file}")

        # Load and parse JSON
        console.print(f"[cyan]Loading {self.agency.upper()} requirements from {requirements_file}[/cyan]")

        with open(requirements_file, 'r') as f:
            data = json.load(f)

        # Convert sections to SectionRequirements objects
        sections = {}
        for key, section_data in data['sections'].items():
            sections[key] = SectionRequirements(**section_data)

        # Convert evaluation criteria
        eval_criteria = {}
        for key, criterion_data in data['evaluation_criteria'].items():
            eval_criteria[key] = EvaluationCriterion(**criterion_data)

        # Convert format specifications
        format_specs = FormatSpecifications(**data['format_specifications'])

        # Create AgencyRequirements object
        self.requirements = AgencyRequirements(
            agency=data['agency'],
            program=data['program'],
            funding_amount=data['funding_amount'],
            duration_months=data['duration_months'],
            description=data['description'],
            sections=sections,
            evaluation_criteria=eval_criteria,
            format_specifications=format_specs,
            special_requirements=data.get('special_requirements', {}),
            submission_requirements=data.get('submission_requirements', {})
        )

        console.print(f"[green]✓ Loaded {len(sections)} sections for {self.requirements.agency} {self.requirements.program}[/green]")

    def get_sections(self) -> Dict[str, SectionRequirements]:
        """Get all section requirements"""
        return self.requirements.sections

    def get_section(self, section_key: str) -> Optional[SectionRequirements]:
        """Get requirements for a specific section"""
        return self.requirements.sections.get(section_key)

    def get_ordered_sections(self) -> list[tuple[str, SectionRequirements]]:
        """Get sections in display order"""
        sections = [(key, section) for key, section in self.requirements.sections.items()]
        return sorted(sections, key=lambda x: x[1].order)

    def get_page_limits(self) -> Dict[str, tuple]:
        """Get page limits for quality checker"""
        limits = {}
        for key, section in self.requirements.sections.items():
            limits[key] = (
                section.min_pages,
                section.max_pages,
                section.min_words,
                section.max_words
            )
        return limits

    def get_required_keywords(self) -> Dict[str, list[str]]:
        """Get required keywords by section"""
        keywords = {}
        for key, section in self.requirements.sections.items():
            keywords[section.name] = section.required_keywords
        return keywords

    def get_section_guidelines(self) -> Dict[str, str]:
        """Get section guidelines for grant agent"""
        guidelines = {}
        for key, section in self.requirements.sections.items():
            guidelines[section.name] = section.guidelines
        return guidelines

    def get_evaluation_criteria(self) -> Dict[str, EvaluationCriterion]:
        """Get evaluation criteria"""
        return self.requirements.evaluation_criteria

    def get_funding_amount(self) -> int:
        """Get total funding amount"""
        return self.requirements.funding_amount

    def get_duration_months(self) -> int:
        """Get project duration in months"""
        return self.requirements.duration_months

    def get_format_specs(self) -> FormatSpecifications:
        """Get format specifications"""
        return self.requirements.format_specifications

    def generate_requirements_text(self) -> str:
        """Generate formatted requirements text for prompts"""
        lines = []

        lines.append(f"# {self.requirements.agency} {self.requirements.program} Requirements")
        lines.append("")
        lines.append(f"**Funding Amount:** ${self.requirements.funding_amount:,}")
        lines.append(f"**Duration:** {self.requirements.duration_months} months")
        lines.append("")

        # Evaluation criteria
        lines.append("## Evaluation Criteria")
        lines.append("")
        for name, criterion in self.requirements.evaluation_criteria.items():
            lines.append(f"### {name.replace('_', ' ').title()} ({criterion.weight*100:.0f}%)")
            lines.append(f"{criterion.description}")
            lines.append("")
            for sub in criterion.sub_criteria:
                lines.append(f"- {sub}")
            lines.append("")

        # Format specifications
        lines.append("## Format Specifications")
        lines.append("")
        specs = self.requirements.format_specifications
        lines.append(f"- Font: {specs.font}, {specs.font_size}pt")
        lines.append(f"- Line spacing: {specs.line_spacing}")
        lines.append(f"- Margins: {specs.margins['top']}\" (all sides)")
        lines.append(f"- Approximately {specs.words_per_page} words per page")
        lines.append("")

        # Special requirements
        if self.requirements.special_requirements:
            lines.append("## Special Requirements")
            lines.append("")
            for key, value in self.requirements.special_requirements.items():
                if isinstance(value, bool):
                    status = "Required" if value else "Not required"
                    lines.append(f"- {key.replace('_', ' ').title()}: {status}")
                else:
                    lines.append(f"- {key.replace('_', ' ').title()}: {value}")
            lines.append("")

        return "\n".join(lines)

    def print_summary(self):
        """Print summary of loaded requirements"""
        console.print("\n" + "="*70)
        console.print(f"[bold cyan]{self.requirements.agency} {self.requirements.program}[/bold cyan]")
        console.print("="*70)
        console.print(f"[yellow]{self.requirements.description}[/yellow]")
        console.print(f"\n💰 Funding: ${self.requirements.funding_amount:,}")
        console.print(f"📅 Duration: {self.requirements.duration_months} months")
        console.print(f"📄 Sections: {len(self.requirements.sections)}")

        console.print("\n[bold]Required Sections:[/bold]")
        for key, section in self.get_ordered_sections():
            required_mark = "✓" if section.required else " "
            console.print(f"  [{required_mark}] {section.order}. {section.name} ({section.min_words}-{section.max_words} words)")

        console.print("\n[bold]Evaluation Criteria:[/bold]")
        for name, criterion in self.requirements.evaluation_criteria.items():
            console.print(f"  • {name.replace('_', ' ').title()}: {criterion.weight*100:.0f}% - {criterion.description}")

        console.print("="*70 + "\n")


def load_agency_requirements(agency: str, templates_dir: str = "agency_templates") -> AgencyLoader:
    """
    Convenience function to load agency requirements

    Args:
        agency: Agency code ('nsf', 'dod', 'nasa')
        templates_dir: Path to agency templates directory

    Returns:
        AgencyLoader instance with loaded requirements
    """
    return AgencyLoader(agency, templates_dir)
