import re
from typing import Dict, List, Tuple, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from src.models import GrantProposal, GrantSection, CompanyContext
from src.agency_loader import AgencyLoader

console = Console()


class QualityChecker:
    """Enhanced quality validation system for grant proposals (multi-agency support)"""

    def __init__(self, agency_loader: Optional[AgencyLoader] = None):
        self.checks = []
        self.suggestions = []
        self.agency_loader = agency_loader

        # Load agency-specific requirements if available
        if self.agency_loader:
            self.page_limits = self.agency_loader.get_page_limits()
            self.required_keywords = self.agency_loader.get_required_keywords()
            self.funding_amount = self.agency_loader.get_funding_amount()
            self.duration_months = self.agency_loader.get_duration_months()
            self.agency_name = self.agency_loader.requirements.agency
        else:
            # Default to NSF requirements for backward compatibility
            self.page_limits = {
                "project_pitch": (1, 2, 400, 800),
                "technical_objectives": (5, 6, 2000, 2400),
                "broader_impacts": (1, 2, 400, 800),
                "commercialization_plan": (2, 3, 800, 1200),
                "budget_justification": (2, 3, 800, 1200),
                "work_plan": (2, 3, 800, 1200),
                "biographical_sketches": (2, 8, 800, 3200),
                "facilities_equipment": (1, 2, 400, 800)
            }
            self.required_keywords = {
                "Project Pitch": ["innovation", "problem", "solution", "market", "Phase I"],
                "Technical Objectives": ["methodology", "risk", "milestone", "feasibility", "TRL"],
                "Broader Impacts": ["societal", "impact", "benefit", "broader"],
                "Commercialization Plan": ["market", "customer", "revenue", "competitive", "commercialization"],
                "Budget and Budget Justification": ["personnel", "equipment", "overhead", "justification"],
                "Work Plan and Timeline": ["month", "milestone", "timeline", "deliverable"],
                "Key Personnel Biographical Sketches": ["education", "experience", "PhD", "publications"],
                "Facilities, Equipment, and Other Resources": ["facilities", "equipment", "resources"]
            }
            self.funding_amount = 275000
            self.duration_months = 6
            self.agency_name = "NSF"

    def auto_trim_section(self, section: GrantSection, max_words: int) -> Tuple[GrantSection, bool]:
        """Auto-trim section to meet page limits while preserving meaning"""
        if section.word_count <= max_words:
            return section, False

        # Trim content intelligently
        words = section.content.split()
        trimmed_content = ' '.join(words[:max_words])

        # Try to end at a sentence boundary
        last_period = trimmed_content.rfind('.')
        if last_period > max_words * 0.9 * 5:  # If we can find a period in the last 10%
            trimmed_content = trimmed_content[:last_period + 1]

        # Add trimming notice
        trimmed_content += "\n\n[Content auto-trimmed to meet NSF page limits]"

        trimmed_section = GrantSection(
            name=section.name,
            content=trimmed_content,
            word_count=len(trimmed_content.split()),
            iteration=section.iteration,
            critique=section.critique,
            refinement_notes=f"{section.refinement_notes or ''} | Auto-trimmed from {section.word_count} to {len(trimmed_content.split())} words"
        )

        return trimmed_section, True

    def check_page_limits(self, proposal: GrantProposal) -> Dict:
        """Check and auto-trim sections exceeding page limits"""
        results = {}
        trimmed_sections = {}

        for section_key, (min_pages, max_pages, min_words, max_words) in self.page_limits.items():
            section = getattr(proposal, section_key)
            count = section.word_count

            status = "✓ Good"
            passed = True
            trimmed = False

            if count < min_words:
                status = f"⚠️  Too short ({count}/{min_words} words)"
                passed = False
                self.suggestions.append(
                    f"**{section.name}**: Add {min_words - count} more words to meet minimum {min_pages}-page requirement. "
                    f"Consider expanding on key points, adding examples, or providing more detail."
                )
            elif count > max_words:
                # Auto-trim
                trimmed_section, was_trimmed = self.auto_trim_section(section, max_words)
                if was_trimmed:
                    trimmed_sections[section_key] = trimmed_section
                    trimmed = True
                    status = f"✂️  Auto-trimmed ({count} → {trimmed_section.word_count} words)"
                    passed = True
                    self.suggestions.append(
                        f"**{section.name}**: Section was auto-trimmed from {count} to {trimmed_section.word_count} words. "
                        f"Review to ensure critical content wasn't removed."
                    )
                else:
                    status = f"✓ Within limit"
                    passed = True

            results[section.name] = {
                "count": count,
                "range": f"{min_words}-{max_words} words ({min_pages}-{max_pages} pages)",
                "status": status,
                "passed": passed,
                "trimmed": trimmed
            }

        return results, trimmed_sections

    def check_required_keywords(self, proposal: GrantProposal) -> Dict:
        """Check for required keywords in each section"""
        results = {}

        section_map = {
            "Project Pitch": "project_pitch",
            "Technical Objectives": "technical_objectives",
            "Broader Impacts": "broader_impacts",
            "Commercialization Plan": "commercialization_plan",
            "Budget and Budget Justification": "budget_justification",
            "Work Plan and Timeline": "work_plan",
            "Key Personnel Biographical Sketches": "biographical_sketches",
            "Facilities, Equipment, and Other Resources": "facilities_equipment"
        }

        for section_name, section_key in section_map.items():
            section = getattr(proposal, section_key)
            keywords = self.required_keywords.get(section_name, [])

            content_lower = section.content.lower()
            found = [kw for kw in keywords if kw.lower() in content_lower]
            missing = [kw for kw in keywords if kw.lower() not in content_lower]

            passed = len(missing) == 0

            if not passed:
                self.suggestions.append(
                    f"**{section.name}**: Missing required keywords: {', '.join(missing)}. "
                    f"These are important for NSF reviewers and should be explicitly addressed."
                )

            results[section.name] = {
                "found": found,
                "missing": missing,
                "coverage": f"{len(found)}/{len(keywords)}",
                "passed": passed
            }

        return results

    def check_budget_total(self, proposal: GrantProposal) -> Dict:
        """Validate that budget totals exactly the target funding amount"""
        budget_content = proposal.budget_justification.content

        # Look for dollar amounts in the budget
        dollar_pattern = r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        amounts = re.findall(dollar_pattern, budget_content)

        # Parse amounts
        parsed_amounts = []
        for amount_str in amounts:
            try:
                amount = float(amount_str.replace(',', ''))
                parsed_amounts.append(amount)
            except ValueError:
                continue

        # Look for total amount
        total_pattern = r'(?:total|sum|grand total)[\s:]+\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)'
        total_match = re.search(total_pattern, budget_content, re.IGNORECASE)

        budget_total = None
        if total_match:
            try:
                budget_total = float(total_match.group(1).replace(',', ''))
            except ValueError:
                pass

        # Check if total matches target funding amount
        target_budget = float(self.funding_amount)
        passed = False
        status = "❌ Budget total not found"

        if budget_total is not None:
            if budget_total == target_budget:
                status = f"✓ Budget totals exactly ${budget_total:,.2f}"
                passed = True
            else:
                difference = budget_total - target_budget
                status = f"⚠️  Budget is ${budget_total:,.2f} (${difference:+,.2f} from target)"
                passed = False
                self.suggestions.append(
                    f"**Budget**: Total is ${budget_total:,.2f} but should be exactly ${target_budget:,.0f}. "
                    f"Adjust line items by ${abs(difference):,.2f} to match {self.agency_name} SBIR Phase I funding limit."
                )
        else:
            self.suggestions.append(
                f"**Budget**: Could not identify budget total. Ensure budget clearly states 'Total: ${target_budget:,.0f}' "
                f"and all line items add up to exactly this amount."
            )

        return {
            "target": target_budget,
            "actual": budget_total,
            "amounts_found": len(parsed_amounts),
            "status": status,
            "passed": passed
        }

    def check_timeline_coverage(self, proposal: GrantProposal) -> Dict:
        """Check that timeline covers full Phase I duration"""
        timeline_content = proposal.work_plan.content.lower()

        # Look for month references
        month_patterns = [
            r'month\s+(\d+)',
            r'm(\d+)',
            r'(\d+)\s*month',
            r'(january|february|march|april|may|june|july|august|september|october|november|december)'
        ]

        months_found = set()
        for pattern in month_patterns:
            matches = re.findall(pattern, timeline_content)
            for match in matches:
                if match.isdigit():
                    month_num = int(match)
                    if 1 <= month_num <= 12:
                        months_found.add(month_num)

        # Check for coverage based on agency duration
        duration = self.duration_months
        has_month_1 = any(str(i) in timeline_content or f'month {i}' in timeline_content for i in [1])
        has_month_last = any(str(i) in timeline_content or f'month {i}' in timeline_content for i in [duration])

        # Count how many months 1-duration are mentioned
        phase1_months = set(range(1, duration + 1))
        mentioned_months = months_found & phase1_months
        coverage = len(mentioned_months)

        passed = coverage >= duration or (has_month_1 and has_month_last)

        if passed:
            status = f"✓ Timeline covers {duration}-month Phase I period"
        else:
            status = f"⚠️  Timeline only mentions {coverage}/{duration} months"
            self.suggestions.append(
                f"**Work Plan**: Timeline should explicitly cover all {duration} months of Phase I. "
                f"Add monthly milestones for months: {', '.join(map(str, phase1_months - mentioned_months))}."
            )

        return {
            "months_mentioned": sorted(list(mentioned_months)),
            "coverage": f"{coverage}/{duration} months",
            "status": status,
            "passed": passed
        }

    def check_team_bios(self, proposal: GrantProposal, company_context: CompanyContext) -> Dict:
        """Ensure all team members have biographical sketches"""
        bio_content = proposal.biographical_sketches.content.lower()
        team_members = company_context.team

        results = []
        all_covered = True

        for member in team_members:
            name = member['name'].lower()
            # Check if name appears in bio section
            found = name in bio_content

            if found:
                # Check for key bio elements (education, background)
                has_education = any(edu in bio_content for edu in ['phd', 'ph.d', 'master', 'bachelor', 'degree', 'university'])
                has_background = 'background' in bio_content or 'experience' in bio_content
                complete = has_education and has_background
            else:
                complete = False
                all_covered = False
                self.suggestions.append(
                    f"**Biographical Sketches**: Missing bio for {member['name']} ({member['role']}). "
                    f"Add a comprehensive 2-page biographical sketch including education, experience, and relevant publications."
                )

            results.append({
                "name": member['name'],
                "role": member['role'],
                "found": found,
                "complete": complete
            })

        passed = all_covered
        status = "✓ All team members have bios" if passed else f"⚠️  {sum(1 for r in results if not r['found'])} team member(s) missing bios"

        return {
            "team_count": len(team_members),
            "bios_found": sum(1 for r in results if r['found']),
            "status": status,
            "passed": passed,
            "details": results
        }

    def check_citations_and_claims(self, proposal: GrantProposal) -> Dict:
        """Flag missing citations or unsubstantiated claims"""
        # Claim indicators that should have citations
        claim_patterns = [
            r'studies show',
            r'research indicates',
            r'according to',
            r'it is estimated',
            r'market size',
            r'industry reports',
            r'\d+%',  # Percentages
            r'\$\d+\.?\d*\s*(?:million|billion|M|B)',  # Market sizes
            r'(?:NASA|DOD|DARPA|NSF|NIH|NOAA)',  # Agency names that might need citations
        ]

        citation_patterns = [
            r'\[[\d,\s]+\]',  # [1], [1,2]
            r'\(\w+\s+et al\.,?\s+\d{4}\)',  # (Author et al., 2023)
            r'\(\w+\s+\d{4}\)',  # (Author 2023)
            r'https?://',  # URLs
        ]

        results = {}
        sections_to_check = {
            "Project Pitch": "project_pitch",
            "Technical Objectives": "technical_objectives",
            "Broader Impacts": "broader_impacts",
            "Commercialization Plan": "commercialization_plan"
        }

        for section_name, section_key in sections_to_check.items():
            section = getattr(proposal, section_key)
            content = section.content

            # Count potential claims
            claims_found = []
            for pattern in claim_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    # Get context around the claim
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end].replace('\n', ' ')
                    claims_found.append(context)

            # Count citations
            citations_found = []
            for pattern in citation_patterns:
                matches = re.findall(pattern, content)
                citations_found.extend(matches)

            # Analysis
            has_claims = len(claims_found) > 0
            has_citations = len(citations_found) > 0

            passed = True
            status = "✓ Good"

            if has_claims and not has_citations:
                status = f"⚠️  {len(claims_found)} claim(s) found, no citations"
                passed = False
                self.suggestions.append(
                    f"**{section.name}**: Found {len(claims_found)} claim(s) without citations. "
                    f"Add references to support statements about market size, research findings, and technical claims."
                )
            elif has_claims and has_citations:
                status = f"✓ {len(claims_found)} claim(s), {len(citations_found)} citation(s)"

            results[section.name] = {
                "claims_found": len(claims_found),
                "citations_found": len(citations_found),
                "status": status,
                "passed": passed,
                "sample_claims": claims_found[:3]  # First 3 claims for review
            }

        return results

    def check_readability(self, proposal: GrantProposal) -> Dict:
        """Check readability and clarity"""
        results = {}

        all_sections = [
            ("Project Pitch", "project_pitch"),
            ("Technical Objectives", "technical_objectives"),
            ("Broader Impacts", "broader_impacts"),
            ("Commercialization Plan", "commercialization_plan"),
            ("Budget and Budget Justification", "budget_justification"),
            ("Work Plan and Timeline", "work_plan"),
        ]

        for section_name, section_key in all_sections:
            section = getattr(proposal, section_key)

            # Simple heuristics for clarity
            sentences = [s.strip() for s in section.content.split('.') if s.strip()]
            if not sentences:
                continue

            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)

            # Check for overly complex sentences
            too_long = avg_sentence_length > 30

            # Check for passive voice (rough heuristic)
            passive_indicators = ['is being', 'was being', 'are being', 'were being', 'be being', 'been being', 'being']
            passive_count = sum(1 for indicator in passive_indicators if indicator in section.content.lower())

            passed = not too_long
            status = "✓ Good readability"

            if too_long:
                status = f"⚠️  Avg sentence length {avg_sentence_length:.1f} words (>30)"
                self.suggestions.append(
                    f"**{section.name}**: Average sentence length is {avg_sentence_length:.1f} words. "
                    f"Consider breaking up complex sentences for better readability."
                )

            results[section.name] = {
                "avg_sentence_length": round(avg_sentence_length, 1),
                "sentence_count": len(sentences),
                "passive_voice_indicators": passive_count,
                "status": status,
                "passed": passed
            }

        return results

    def generate_quality_report(self, proposal: GrantProposal, company_context: CompanyContext) -> str:
        """Generate comprehensive quality report with improvement suggestions"""
        report = []

        report.append("# NSF SBIR Phase I Proposal - Quality Report")
        report.append("")
        report.append(f"**Company:** {proposal.company_name}")
        report.append(f"**Total Word Count:** {proposal.total_word_count:,}")
        report.append(f"**Generation Cost:** ${proposal.total_cost:.2f}")
        report.append("")
        report.append("---")
        report.append("")

        # Reset suggestions
        self.suggestions = []

        # Run all checks
        page_results, trimmed_sections = self.check_page_limits(proposal)
        keyword_results = self.check_required_keywords(proposal)
        budget_result = self.check_budget_total(proposal)
        timeline_result = self.check_timeline_coverage(proposal)
        bio_result = self.check_team_bios(proposal, company_context)
        citation_results = self.check_citations_and_claims(proposal)
        readability_results = self.check_readability(proposal)

        # Summary
        all_checks = []
        all_checks.extend([r["passed"] for r in page_results.values()])
        all_checks.extend([r["passed"] for r in keyword_results.values()])
        all_checks.append(budget_result["passed"])
        all_checks.append(timeline_result["passed"])
        all_checks.append(bio_result["passed"])
        all_checks.extend([r["passed"] for r in citation_results.values()])
        all_checks.extend([r["passed"] for r in readability_results.values()])

        passed_count = sum(all_checks)
        total_count = len(all_checks)
        pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0

        report.append("## Executive Summary")
        report.append("")
        report.append(f"**Overall Quality Score:** {pass_rate:.1f}% ({passed_count}/{total_count} checks passed)")
        report.append("")

        if pass_rate >= 90:
            report.append("✅ **Status:** EXCELLENT - Proposal meets NSF quality standards")
        elif pass_rate >= 75:
            report.append("⚠️  **Status:** GOOD - Minor improvements recommended")
        elif pass_rate >= 60:
            report.append("⚠️  **Status:** FAIR - Several areas need attention")
        else:
            report.append("❌ **Status:** NEEDS WORK - Significant revisions required")

        report.append("")
        report.append("---")
        report.append("")

        # Detailed Results
        report.append("## Detailed Quality Checks")
        report.append("")

        # 1. Page Limits
        report.append("### 1. Page Limits and Word Counts")
        report.append("")
        for section_name, data in page_results.items():
            symbol = "✓" if data["passed"] else "⚠️"
            report.append(f"- **{symbol} {section_name}:** {data['count']} words (target: {data['range']}) - {data['status']}")
        report.append("")

        # 2. Required Keywords
        report.append("### 2. Required Keywords")
        report.append("")
        for section_name, data in keyword_results.items():
            symbol = "✓" if data["passed"] else "⚠️"
            report.append(f"- **{symbol} {section_name}:** {data['coverage']} keywords found")
            if data["missing"]:
                report.append(f"  - Missing: {', '.join(data['missing'])}")
        report.append("")

        # 3. Budget
        report.append("### 3. Budget Validation")
        report.append("")
        report.append(f"- {budget_result['status']}")
        if budget_result['actual']:
            report.append(f"- Target: ${budget_result['target']:,.2f}")
            report.append(f"- Actual: ${budget_result['actual']:,.2f}")
        report.append("")

        # 4. Timeline
        report.append("### 4. Timeline Coverage")
        report.append("")
        report.append(f"- {timeline_result['status']}")
        report.append(f"- Months mentioned: {', '.join(map(str, timeline_result['months_mentioned'])) if timeline_result['months_mentioned'] else 'None identified'}")
        report.append("")

        # 5. Team Bios
        report.append("### 5. Team Member Biographical Sketches")
        report.append("")
        report.append(f"- {bio_result['status']}")
        for detail in bio_result['details']:
            symbol = "✓" if detail['complete'] else "❌"
            report.append(f"  - {symbol} {detail['name']} ({detail['role']})")
        report.append("")

        # 6. Citations
        report.append("### 6. Citations and Supporting Evidence")
        report.append("")
        for section_name, data in citation_results.items():
            symbol = "✓" if data["passed"] else "⚠️"
            report.append(f"- **{symbol} {section_name}:** {data['status']}")
        report.append("")

        # 7. Readability
        report.append("### 7. Readability Analysis")
        report.append("")
        for section_name, data in readability_results.items():
            symbol = "✓" if data["passed"] else "⚠️"
            report.append(f"- **{symbol} {section_name}:** {data['status']}")
        report.append("")

        # Improvement Suggestions
        if self.suggestions:
            report.append("---")
            report.append("")
            report.append("## 🎯 Recommended Improvements")
            report.append("")
            for i, suggestion in enumerate(self.suggestions, 1):
                report.append(f"{i}. {suggestion}")
            report.append("")

        # Next Steps
        report.append("---")
        report.append("")
        report.append("## Next Steps")
        report.append("")
        if pass_rate >= 90:
            report.append("1. Review auto-trimmed sections if any")
            report.append("2. Add specific citations where needed")
            report.append("3. Final proofreading pass")
            report.append("4. Submit proposal to NSF")
        else:
            report.append("1. Address all items in 'Recommended Improvements' section")
            report.append("2. Re-run quality checker after revisions")
            report.append("3. Have proposal reviewed by domain expert")
            report.append("4. Revise and resubmit for quality check")

        return "\n".join(report), trimmed_sections

    def validate_proposal(self, proposal: GrantProposal, company_context: CompanyContext = None) -> Dict:
        """Run all validation checks and display results"""
        console.print("\n[bold blue]🔍 Running Enhanced Quality Checks...[/bold blue]\n")

        # Generate report
        if company_context:
            report_text, trimmed_sections = self.generate_quality_report(proposal, company_context)
        else:
            # For backward compatibility
            self.suggestions = []
            page_results, trimmed_sections = self.check_page_limits(proposal)
            keyword_results = self.check_required_keywords(proposal)

            all_passed = (
                all(r["passed"] for r in page_results.values()) and
                all(r["passed"] for r in keyword_results.values())
            )

            report_text = "Quality check completed (limited mode - no company context provided)"

        # Display report
        console.print(Panel(
            Markdown(report_text),
            title="Quality Assessment Report",
            border_style="blue"
        ))

        # Apply trimmed sections to proposal
        for section_key, trimmed_section in trimmed_sections.items():
            setattr(proposal, section_key, trimmed_section)

        return {
            "report": report_text,
            "trimmed_sections": list(trimmed_sections.keys()),
            "suggestions_count": len(self.suggestions),
            "overall_passed": len(self.suggestions) == 0
        }
