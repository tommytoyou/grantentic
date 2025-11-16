from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from src.models import GrantProposal

console = Console()


class QualityChecker:
    """Validates grant proposal against NSF SBIR requirements"""
    
    def __init__(self):
        self.checks = []
    
    def check_word_counts(self, proposal: GrantProposal) -> dict:
        """Verify sections are within recommended word counts"""
        ranges = {
            "project_pitch": (400, 800),      # 1-2 pages
            "technical_objectives": (2000, 2500),  # 5-6 pages
            "broader_impacts": (400, 800),    # 1-2 pages
            "commercialization_plan": (800, 1200)  # 2-3 pages
        }
        
        results = {}
        for section_key, (min_words, max_words) in ranges.items():
            section = getattr(proposal, section_key)
            count = section.word_count
            
            if count < min_words:
                status = "⚠️  Too short"
                passed = False
            elif count > max_words:
                status = "⚠️  Too long"
                passed = False
            else:
                status = "✓ Good"
                passed = True
            
            results[section.name] = {
                "count": count,
                "range": f"{min_words}-{max_words}",
                "status": status,
                "passed": passed
            }
        
        return results
    
    def check_required_elements(self, proposal: GrantProposal) -> dict:
        """Check for required proposal elements"""
        required_keywords = {
            "Project Pitch": ["problem", "solution", "innovation", "market", "Phase I"],
            "Technical Objectives": ["methodology", "risk", "milestone", "feasibility", "TRL"],
            "Broader Impacts": ["societal", "impact", "benefit"],
            "Commercialization Plan": ["market", "customer", "revenue", "competitive"]
        }
        
        results = {}
        for section_key in ["project_pitch", "technical_objectives", "broader_impacts", "commercialization_plan"]:
            section = getattr(proposal, section_key)
            keywords = required_keywords[section.name]
            
            content_lower = section.content.lower()
            found = [kw for kw in keywords if kw.lower() in content_lower]
            missing = [kw for kw in keywords if kw.lower() not in content_lower]
            
            results[section.name] = {
                "found": found,
                "missing": missing,
                "coverage": f"{len(found)}/{len(keywords)}",
                "passed": len(missing) == 0
            }
        
        return results
    
    def check_clarity(self, proposal: GrantProposal) -> dict:
        """Check for clarity indicators"""
        results = {}
        
        for section_key in ["project_pitch", "technical_objectives", "broader_impacts", "commercialization_plan"]:
            section = getattr(proposal, section_key)
            
            # Simple heuristics for clarity
            sentences = section.content.split('.')
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
            
            # Check for overly complex sentences
            too_long = avg_sentence_length > 30
            
            results[section.name] = {
                "avg_sentence_length": round(avg_sentence_length, 1),
                "status": "⚠️  Sentences may be too complex" if too_long else "✓ Good readability",
                "passed": not too_long
            }
        
        return results
    
    def validate_proposal(self, proposal: GrantProposal) -> dict:
        """Run all validation checks"""
        console.print("\n[bold blue]🔍 Running Quality Checks...[/bold blue]\n")
        
        word_count_results = self.check_word_counts(proposal)
        element_results = self.check_required_elements(proposal)
        clarity_results = self.check_clarity(proposal)
        
        # Display word count results
        table = Table(title="📊 Word Count Validation")
        table.add_column("Section", style="cyan")
        table.add_column("Word Count", justify="right")
        table.add_column("Target Range", justify="right")
        table.add_column("Status")
        
        for section_name, data in word_count_results.items():
            table.add_row(
                section_name,
                str(data["count"]),
                data["range"],
                data["status"]
            )
        
        console.print(table)
        
        # Display required elements
        table2 = Table(title="📋 Required Elements Check")
        table2.add_column("Section", style="cyan")
        table2.add_column("Coverage", justify="center")
        table2.add_column("Status")
        
        for section_name, data in element_results.items():
            status = "✓ All present" if data["passed"] else f"⚠️  Missing: {', '.join(data['missing'])}"
            table2.add_row(section_name, data["coverage"], status)
        
        console.print(table2)
        
        # Display clarity check
        table3 = Table(title="📖 Readability Check")
        table3.add_column("Section", style="cyan")
        table3.add_column("Avg Sentence Length", justify="right")
        table3.add_column("Status")
        
        for section_name, data in clarity_results.items():
            table3.add_row(
                section_name,
                str(data["avg_sentence_length"]),
                data["status"]
            )
        
        console.print(table3)
        
        # Overall assessment
        all_passed = (
            all(r["passed"] for r in word_count_results.values()) and
            all(r["passed"] for r in element_results.values()) and
            all(r["passed"] for r in clarity_results.values())
        )
        
        if all_passed:
            console.print(Panel(
                "[bold green]✅ Proposal passes all quality checks![/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                "[bold yellow]⚠️  Some quality checks need attention. Review above for details.[/bold yellow]",
                border_style="yellow"
            ))
        
        return {
            "word_counts": word_count_results,
            "required_elements": element_results,
            "clarity": clarity_results,
            "overall_passed": all_passed
        }
