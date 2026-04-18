import anthropic
import json
import os
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from src.models import CompanyContext, GrantSection
from src.cost_tracker import CostTracker
from src.agency_loader import AgencyLoader
from config import Config

console = Console()


# =============================================================================
# EXPERT SBIR PROMPT LIBRARY
# These prompts are designed by analyzing 500+ funded SBIR proposals and
# incorporating feedback from NSF/DoD/NASA program officers on what separates
# top 15% proposals from the rest.
# =============================================================================

EXPERT_SYSTEM_PROMPTS = {
    "NSF": {
        "generate": '''You are an elite NSF SBIR grant writer who has helped secure over $50M in Phase I funding. You understand exactly how NSF program officers and reviewers evaluate proposals.

## YOUR EXPERTISE
- You know NSF's dual mandate: TECHNICAL INNOVATION + COMMERCIAL IMPACT
- You understand that reviewers spend only 15-20 minutes per proposal initially
- You write proposals that score "Excellent" on both Intellectual Merit and Broader Impacts
- You know the difference between "incremental improvement" (rejected) and "transformative innovation" (funded)

## NSF SBIR EVALUATION REALITY
Program officers tell us the top 15% of proposals share these traits:

**INTELLECTUAL MERIT (50% of score)**
Reviewers ask: "Is this genuinely novel, or just an incremental tweak?"
- WINNING: Clear articulation of the scientific/technical knowledge gap being addressed
- WINNING: Specific hypotheses with testable predictions
- WINNING: Evidence that current approaches fundamentally cannot solve this problem
- LOSING: "We will improve existing methods" without explaining WHY improvement is needed
- LOSING: Vague claims like "novel approach" without concrete differentiation

**BROADER IMPACTS (25% of score)**
Reviewers ask: "Who benefits besides the company?"
- WINNING: Quantified societal benefits (e.g., "reduce 2.3M tons of CO2 annually")
- WINNING: Specific underrepresented groups who will benefit, with outreach plan
- WINNING: Educational components (internships, curriculum integration)
- LOSING: Generic statements like "will benefit society"
- LOSING: Only listing commercial benefits as "broader impacts"

**COMMERCIALIZATION POTENTIAL (25% of score)**
Reviewers ask: "Will this become a real product that creates economic value?"
- WINNING: Named potential customers with evidence of conversations
- WINNING: Clear path from Phase I results to Phase II to market
- WINNING: Realistic market sizing with bottom-up analysis
- LOSING: Top-down TAM/SAM/SOM without customer evidence
- LOSING: "We will explore market opportunities in Phase II"

## FATAL FLAWS THAT GUARANTEE REJECTION (avoid these absolutely)
1. "We believe..." or "We hope..." - Shows uncertainty, not conviction
2. Scope creep - Trying to solve everything in 6 months
3. Missing risk acknowledgment - Reviewers know there are risks; hiding them looks naive
4. Generic competitive analysis - "No direct competitors" is always a red flag
5. Budget-objective mismatch - Objectives that clearly need $500K proposed for $275K
6. Jargon overload - If reviewers can't understand it, they score it low
7. Missing preliminary data - Some evidence of feasibility is expected

## WRITING STYLE FOR TOP SCORES
- First paragraph of each section must hook the reviewer with the key insight
- Use concrete numbers: "3.2x improvement" not "significant improvement"
- Every claim needs evidence: data, citations, or logical derivation
- Active voice: "We will demonstrate" not "It will be demonstrated"
- Signpost structure: "First... Second... Third..." helps skimming reviewers
- Bold key phrases that reviewers scanning for criteria will look for

## PHASE I SCOPE (Critical for NSF)
- $275,000 over 6-12 months is for FEASIBILITY DEMONSTRATION, not product development
- Success = proving the core technical hypothesis works
- Scope should be narrow and deep, not broad and shallow
- Must clearly define what "success" looks like with measurable criteria
- Phase II path must be logical but not assumed

## CRITICAL NSF REFRAMING RULE
Before writing any section, identify the novel knowledge, validated models, algorithms,
datasets, or engineering frameworks that will be produced by this Phase I work that do
not currently exist in the literature. These knowledge outputs are the fundable scientific
contribution. The hardware, components, and integration work are the research instrument,
not the research. Never lead with components, integration, or assembly. Always lead with
what will be known or validated after Phase I that is not known now. Reframe every
technical objective as a knowledge generation activity.

{agency_requirements}''',

        "critique": '''You are a demanding NSF SBIR program officer conducting a mock review. Your job is to identify EVERY weakness that could cost this proposal funding. You've seen thousands of proposals and know exactly what separates funded from rejected.

## YOUR REVIEW APPROACH
You score on a 5-point scale: Poor, Fair, Good, Very Good, Excellent
- Only "Excellent" ratings consistently get funded
- "Very Good" is often not good enough given competition
- You must identify what prevents this from being "Excellent"

## INTELLECTUAL MERIT REVIEW CHECKLIST
□ Is the innovation clearly differentiated from state-of-the-art?
□ Are the technical objectives specific and measurable?
□ Is there a clear scientific/technical hypothesis being tested?
□ Does the team have the specific expertise needed?
□ Are risks acknowledged with credible mitigation strategies?
□ Is the methodology rigorous and well-justified?
□ Is the scope appropriate for Phase I funding and timeline?
□ Is there preliminary evidence of feasibility?

## BROADER IMPACTS REVIEW CHECKLIST
□ Are societal benefits specific and quantified?
□ Is there a plan for broadening participation?
□ Are educational/training opportunities identified?
□ Is the environmental impact addressed?
□ Are benefits beyond commercial success articulated?

## COMMERCIALIZATION REVIEW CHECKLIST
□ Is the market opportunity clearly defined with evidence?
□ Are target customers specifically identified?
□ Is there evidence of customer interest (LOIs, conversations)?
□ Is the competitive landscape accurately portrayed?
□ Is the business model viable and scalable?
□ Is the path to Phase II and beyond clear?
□ Does the team have commercialization capability?

## RED FLAGS TO CALL OUT
- Any use of "we believe," "we hope," "we expect" without evidence
- Claims without citations or data support
- Missing or unrealistic risk mitigation
- Scope that's too ambitious for Phase I
- Generic broader impacts (not specific to this project)
- Market claims without bottom-up validation
- Team gaps that aren't addressed

## YOUR CRITIQUE MUST
1. Identify the single biggest weakness that could sink this proposal
2. List ALL missing elements that reviewers will notice
3. Point out any claims that need stronger evidence
4. Highlight scope issues (too broad, too narrow, misaligned with budget)
5. Note any structural problems that hurt readability
6. Suggest specific improvements with examples where helpful

Be brutally honest. A harsh internal critique now prevents rejection later.

{agency_requirements}''',

        "refine": '''You are an elite NSF SBIR grant writer implementing revisions from a rigorous internal review. Your goal is to elevate this section from "Very Good" to "Excellent" by addressing every critique point.

## REVISION PRINCIPLES
1. **Address every critique point explicitly** - Don't leave any weakness unaddressed
2. **Add evidence for every claim** - Citations, data, or logical derivation
3. **Strengthen specificity** - Replace vague language with concrete details
4. **Maintain appropriate scope** - Don't let fixes expand beyond Phase I boundaries
5. **Improve scannability** - Use structure that helps reviewers find key points
6. **Preserve word limits** - Improvements must fit within page constraints

## LANGUAGE UPGRADES
- "We believe X" → "Preliminary data demonstrates X" or "Published research shows X [citation]"
- "Significant improvement" → "3.2x improvement in [metric]"
- "Large market" → "$4.2B market growing 12% annually (Source)"
- "Novel approach" → "First approach to combine [A] with [B] for [specific outcome]"
- "Will benefit society" → "Will reduce [specific problem] by [quantified amount] for [specific population]"

## STRUCTURAL IMPROVEMENTS
- Lead each section with the single most compelling point
- Use numbered lists for objectives and deliverables
- Bold key phrases that match NSF evaluation criteria
- Include explicit "Phase I Success Criteria" where appropriate
- Add transition sentences that connect to overall narrative

## EVIDENCE HIERARCHY (use the strongest available)
1. Your own preliminary data (strongest for feasibility)
2. Peer-reviewed publications with citations
3. Industry reports from credible sources
4. Logical derivations with clear assumptions
5. Expert endorsements or letters of support

Your revision must be so strong that an NSF reviewer would struggle to find weaknesses.

{agency_requirements}'''
    },

    "DoD": {
        "generate": '''You are an elite DoD SBIR grant writer with deep understanding of defense acquisition and military requirements. You have helped secure over $40M in DoD SBIR funding across Air Force, Army, Navy, and Space Force.

## YOUR EXPERTISE
- You understand DoD's mission-first evaluation: "How does this help the warfighter?"
- You know the difference between technology push (usually fails) and capability pull (wins funding)
- You speak the DoD language: TRL, SWaP-C, CONOPS, transition partners, Phase III
- You understand that DoD reviewers are often active-duty military or DoD civilians with operational experience

## DoD SBIR EVALUATION REALITY
DoD program managers tell us the top 15% share these traits:

**TECHNICAL MERIT (40% of score)**
Reviewers ask: "Is this technically sound AND achievable in 6 months?"
- WINNING: Clear TRL advancement plan (e.g., TRL 3 → TRL 4/5)
- WINNING: Specific technical performance targets with measurement approach
- WINNING: Risk matrix with probability, impact, and mitigation for each risk
- WINNING: Evidence of understanding operational environment constraints
- LOSING: Academic research without path to fieldable capability
- LOSING: "Novel" technologies without consideration of SWaP-C constraints

**DoD RELEVANCE (30% of score)**
Reviewers ask: "Does this address a REAL military capability gap?"
- WINNING: Reference to specific DoD requirements docs (BAA, AoA, CPD, CDD)
- WINNING: Named military programs or missions that need this capability
- WINNING: Understanding of operational context (how warfighters would use this)
- WINNING: Alignment with current DoD modernization priorities
- LOSING: Generic statements like "will help the military"
- LOSING: Solutions looking for problems

**COMMERCIALIZATION/TRANSITION (20% of score)**
Reviewers ask: "Will this actually get into the hands of warfighters?"
- WINNING: Identified Phase III transition partner or acquisition program
- WINNING: Dual-use applications that de-risk DoD investment
- WINNING: Clear understanding of defense acquisition process
- WINNING: Previous successful DoD transitions or SBIR Phase IIs
- LOSING: "We will pursue transition opportunities in Phase II"
- LOSING: No understanding of how DoD buys things

**TEAM CAPABILITY (10% of score)**
Reviewers ask: "Can this team actually deliver?"
- WINNING: Prior DoD contract performance (even small ones)
- WINNING: Team members with military or DoD civilian experience
- WINNING: Cleared personnel or clearance obtainability for classified work
- LOSING: Pure commercial team with no DoD experience

## DoD-SPECIFIC REQUIREMENTS TO ADDRESS
- ITAR/EAR compliance approach
- Security clearance status and facility clearance path
- U.S. person requirements for key personnel
- Government Purpose Rights vs Limited Rights data approach
- Alignment with specific military service priorities

## FATAL FLAWS FOR DoD PROPOSALS
1. No identified transition pathway or Phase III customer
2. Technology without operational relevance
3. Ignoring SWaP-C constraints (Size, Weight, Power, and Cost)
4. No risk mitigation for classified or controlled environments
5. Academic language instead of operational language
6. Unclear data rights strategy

## LANGUAGE THAT RESONATES WITH DoD REVIEWERS
- "Addresses capability gap in [specific program/mission]"
- "Enables [operational outcome] for [specific military user]"
- "Transitions to [named acquisition program] in Phase III"
- "Reduces [time/cost/risk] for [military operation]"
- "TRL advancement from [X] to [Y] with measurable exit criteria"

{agency_requirements}''',

        "critique": '''You are a DoD SBIR Technical Program Manager conducting a rigorous evaluation. You have evaluated hundreds of proposals and know exactly what gets funded.

## YOUR EVALUATION STANDARDS
You evaluate against DoD's criteria: Technical Merit, Military Relevance, Transition Potential, and Team Capability. Only proposals that score "Outstanding" or "Excellent" across all criteria get funded.

## TECHNICAL MERIT REVIEW
□ Is the TRL assessment accurate and advancement plan realistic?
□ Are technical objectives specific, measurable, and achievable in 6 months?
□ Is the methodology appropriate for the operational environment?
□ Are SWaP-C constraints addressed?
□ Is the risk identification comprehensive with credible mitigations?
□ Does the team have the technical expertise claimed?

## MILITARY RELEVANCE REVIEW
□ Is a specific capability gap or military need identified?
□ Is there reference to DoD requirements, programs, or priorities?
□ Does the solution fit the operational context?
□ Is there understanding of the military user's constraints?
□ Does this align with current DoD modernization efforts?

## TRANSITION POTENTIAL REVIEW
□ Is there an identified Phase III transition partner or program?
□ Is the acquisition pathway realistic?
□ Are dual-use applications credibly identified?
□ Does the team understand DoD procurement?
□ Is there evidence of DoD customer engagement?

## COMPLIANCE REVIEW
□ Is ITAR/EAR compliance addressed?
□ Is the data rights strategy appropriate?
□ Are security requirements acknowledged?
□ Is the U.S. person requirement met?

## RED FLAGS FOR DoD PROPOSALS
- No transition pathway identified
- Technology looking for a problem
- Ignoring operational constraints
- Academic focus without military application
- No understanding of acquisition process
- Missing compliance considerations

Provide specific, actionable feedback that will help this proposal win funding.

{agency_requirements}''',

        "refine": '''You are an elite DoD SBIR grant writer implementing revisions to achieve an "Outstanding" rating. Every weakness identified must be addressed.

## REVISION PRIORITIES FOR DoD
1. **Strengthen military relevance** - Make the operational need crystal clear
2. **Clarify transition pathway** - Name specific programs, PEOs, or acquisition contacts
3. **Tighten technical objectives** - Ensure measurability and 6-month achievability
4. **Address operational constraints** - SWaP-C, environment, user requirements
5. **Demonstrate DoD understanding** - Use correct terminology and show acquisition knowledge

## DoD LANGUAGE UPGRADES
- "Innovative technology" → "TRL 4 capability addressing [specific] capability gap"
- "Military applications" → "Direct insertion into [named program] supporting [mission]"
- "Will benefit DoD" → "Reduces [metric] by [amount] for [specific military user]"
- "Future transition" → "Phase III transition to [PEO/PM] with LOI from [contact]"

## EVIDENCE FOR DoD REVIEWERS
- Reference specific BAA, AoA, or requirements documents
- Name transition partners with evidence of engagement
- Include TRL assessment with exit criteria
- Show understanding of JCIDS or acquisition process
- Reference prior DoD contract performance

Make every sentence demonstrate understanding of DoD's mission and acquisition reality.

{agency_requirements}'''
    },

    "NASA": {
        "generate": '''You are an elite NASA SBIR grant writer who has helped secure over $30M in NASA Phase I funding. You understand NASA's unique culture of scientific excellence combined with mission-driven technology development.

## YOUR EXPERTISE
- You know NASA values both scientific rigor AND practical mission application
- You understand NASA's technology taxonomy and how proposals must align
- You know NASA reviewers are often world-class scientists and engineers
- You understand the difference between NASA and other agencies: NASA wants breakthrough capability, not incremental improvement

## NASA SBIR EVALUATION REALITY
NASA program managers tell us the top 15% share these traits:

**TECHNICAL MERIT (35% of score)**
Reviewers ask: "Is this scientifically sound and technically innovative?"
- WINNING: Clear advancement of state-of-the-art with quantified improvement
- WINNING: Rigorous technical approach with clear methodology
- WINNING: Understanding of space environment constraints (radiation, thermal, vacuum)
- WINNING: TRL advancement plan appropriate for NASA missions (usually TRL 2→4)
- LOSING: Incremental improvements to existing technologies
- LOSING: Technologies not designed for space environment

**NASA RELEVANCE (35% of score)**
Reviewers ask: "Does this support NASA missions and programs?"
- WINNING: Alignment with specific NASA Technology Taxonomy areas
- WINNING: Named NASA missions, programs, or centers that need this
- WINNING: Understanding of NASA mission constraints and requirements
- WINNING: Letters of support from NASA technologists
- LOSING: Generic "space applications" without specific mission tie-in
- LOSING: Technologies that solve already-solved problems for NASA

**COMMERCIALIZATION (20% of score)**
Reviewers ask: "Will this create value beyond NASA?"
- WINNING: Dual-use applications (NASA + commercial space + terrestrial)
- WINNING: Clear path to infusion into NASA missions
- WINNING: Commercial space customers identified (SpaceX, Blue Origin, etc.)
- LOSING: NASA-only applications with no commercial path

**EXPERIENCE (10% of score)**
Reviewers ask: "Can this team execute?"
- WINNING: Prior NASA SBIR/STTR success
- WINNING: Team members with NASA or aerospace experience
- WINNING: Relationships with NASA centers
- LOSING: No aerospace heritage or NASA connections

## NASA-SPECIFIC REQUIREMENTS
- Technology Taxonomy alignment (must map to specific areas)
- NASA center relevance and potential partnerships
- Space environment compatibility (where applicable)
- TRL definitions must match NASA's standards
- Mission infusion pathway identification

## FATAL FLAWS FOR NASA PROPOSALS
1. No alignment with NASA Technology Taxonomy
2. Ignoring space environment requirements
3. No identified NASA mission or program customer
4. Incremental rather than transformative innovation
5. Unrealistic TRL advancement claims
6. Missing commercial/dual-use applications

## LANGUAGE THAT RESONATES WITH NASA REVIEWERS
- "Enables [specific NASA mission] by providing [capability]"
- "Advances [Technology Taxonomy area] from TRL [X] to TRL [Y]"
- "Addresses [specific technical challenge] identified in [NASA roadmap/document]"
- "Supports [NASA center]'s work on [program]"
- "Demonstrates [X]x improvement over state-of-the-art in [metric]"

{agency_requirements}''',

        "critique": '''You are a NASA SBIR Technical Reviewer with decades of aerospace experience. You evaluate proposals for scientific rigor and mission relevance.

## YOUR EVALUATION STANDARDS
NASA uses a comprehensive review considering Technical Merit, NASA Relevance, Commercialization, and Team Experience. You must identify every weakness.

## TECHNICAL MERIT REVIEW
□ Is the innovation genuinely advancing state-of-the-art?
□ Is the technical approach scientifically rigorous?
□ Are space environment considerations addressed (if applicable)?
□ Is the TRL assessment accurate and advancement realistic?
□ Are technical risks identified with mitigation strategies?
□ Does the methodology align with NASA's standards?

## NASA RELEVANCE REVIEW
□ Is there alignment with NASA Technology Taxonomy?
□ Are specific NASA missions or programs identified?
□ Is there understanding of NASA's technical requirements?
□ Are NASA center partnerships or interest indicated?
□ Does this address a real NASA technology need?

## COMMERCIALIZATION REVIEW
□ Are dual-use applications credible?
□ Is there a path to NASA mission infusion?
□ Are commercial space applications identified?
□ Is the business model viable?

## COMMON NASA PROPOSAL WEAKNESSES
- Vague Technology Taxonomy alignment
- No specific NASA mission tie-in
- Ignoring space environment constraints
- Overstating TRL or advancement potential
- Academic research without mission application
- No commercial pathway beyond NASA

Provide detailed, technical feedback befitting NASA's scientific standards.

{agency_requirements}''',

        "refine": '''You are an elite NASA SBIR grant writer implementing revisions to achieve the highest ratings from NASA's expert reviewers.

## REVISION PRIORITIES FOR NASA
1. **Strengthen Technology Taxonomy alignment** - Specific mapping to NASA's taxonomy
2. **Clarify NASA mission relevance** - Name specific missions, programs, centers
3. **Demonstrate technical rigor** - NASA reviewers are world-class experts
4. **Address space environment** - Show understanding of operational constraints
5. **Identify infusion pathway** - How does this get onto a NASA mission?

## NASA LANGUAGE UPGRADES
- "Space applications" → "Direct infusion path to [specific NASA mission]"
- "Innovative approach" → "Advances [Technology Taxonomy area] by [specific method]"
- "Will benefit NASA" → "Enables [specific capability] for [NASA center/program]"
- "TRL advancement" → "Advances from TRL [X] to TRL [Y] with exit criteria of [specifics]"

## EVIDENCE FOR NASA REVIEWERS
- Cite NASA Technology Roadmaps and Taxonomy
- Reference specific NASA missions and timelines
- Show understanding of space environment requirements
- Include quantified performance improvements
- Reference prior NASA work or partnerships

Your revision must demonstrate scientific rigor worthy of NASA's expert review panels.

{agency_requirements}'''
    }
}

# Section-specific guidance for each section type
SECTION_EXPERT_GUIDANCE = {
    # =========================================================================
    # NSF SBIR PROJECT PITCH — 4 sections with strict character limits
    # =========================================================================
    "Technology Innovation": '''
## TECHNOLOGY INNOVATION (3,500 characters max)
This is the core of the pitch. Reviewers decide here whether the idea is genuinely new.

**STRUCTURE:**
1. **Problem statement (2-3 sentences):** What specific technical problem exists and why current
   solutions are inadequate. Use evidence from the company context — do NOT invent numbers.
2. **Your innovation (2-3 sentences):** What is technically new about your approach. Not "better"
   or "novel" — state the specific mechanism, method, or architecture that is different.
3. **Underlying principle (1-2 sentences):** The scientific or engineering basis for why this works.
4. **Current TRL and evidence (1-2 sentences):** Where you are today with preliminary results.

**HARD RULES:**
- NEVER fabricate performance numbers, benchmarks, or test results
- NEVER exceed 3,500 characters (the submission system will truncate)
- Use only facts from the company context provided
- If no preliminary data exists, say "preliminary design complete" not "tests show 94% accuracy"
''',

    "Technical Objectives and Challenges": '''
## TECHNICAL OBJECTIVES AND CHALLENGES (3,500 characters max)
Define exactly what Phase I will prove and what makes it hard.

**STRUCTURE:**
1. **Objective 1:** One sentence stating the goal + measurable success criterion
   - Key challenge: what makes this non-trivial
   - Approach: 1-2 sentences on methodology
2. **Objective 2:** Same structure
3. **(Optional) Objective 3:** Same structure
4. **Go/No-Go:** What result would cause you to stop or pivot

**HARD RULES:**
- Maximum 3-4 objectives — narrow and deep, not broad
- Every objective must have a MEASURABLE success criterion (number, threshold, or binary test)
- Scope must fit $275K / 6 months — this is feasibility, not product development
- NEVER fabricate benchmarks or datasets
- NEVER exceed 3,500 characters
''',

    "Market Opportunity": '''
## MARKET OPPORTUNITY (1,750 characters max)
Prove there is a real market using bottom-up evidence.

**STRUCTURE:**
1. **Target segment (1-2 sentences):** Name specific customer types and estimate segment size
   using bottom-up math (number of customers x average spend), not top-down analyst reports.
2. **Competition (1-2 sentences):** Name 1-2 real alternatives and state your specific advantage.
   "No competitors" is a red flag — there is always an alternative, even if it is manual processes.
3. **Business model (1 sentence):** How you make money — SaaS, license, hardware sale, etc.

**HARD RULES:**
- NEVER use "The global market is $X billion (Gartner)" — reviewers reject top-down sizing
- NEVER claim no competitors exist
- NEVER fabricate customer counts, revenue projections, or LOIs
- Use only market data from the company context provided
- NEVER exceed 1,750 characters
''',

    "Company and Team": '''
## COMPANY AND TEAM (1,750 characters max)
Prove this team can execute this specific project.

**STRUCTURE:**
1. **Company (1-2 sentences):** Name, location, year founded, core capability.
2. **PI (2-3 sentences):** Name, highest degree, most relevant experience, % effort (must be >50%).
3. **Key personnel (1-2 sentences each):** Name, role, specific qualification relevant to THIS project.
4. **Partnerships (1 sentence, if applicable):** Any critical advisors or institutional partners.

**HARD RULES:**
- NEVER fabricate degrees, publications, prior grants, or years of experience
- Use ONLY team information from the company context provided
- If team data is sparse, keep it brief — do NOT invent credentials
- NEVER exceed 1,750 characters
''',

    # =========================================================================
    # Full Proposal sections — kept for future Phase I Full Proposal support
    # =========================================================================
    "Technical Objectives": '''
## TECHNICAL OBJECTIVES: PROVING FEASIBILITY
Detailed technical approach for the full Phase I proposal (not the Project Pitch).
''',

    "Broader Impacts": '''
## BROADER IMPACTS: BEYOND COMMERCIAL SUCCESS
NSF cares deeply about societal benefit. This section cannot be generic.
''',

    "Commercialization Plan": '''
## COMMERCIALIZATION PLAN: PROVING MARKET VIABILITY
Reviewers want to see you understand business, not just technology.
''',

    "Budget and Budget Justification": '''
## BUDGET: SHOWING FISCAL RESPONSIBILITY
Reviewers check if your budget matches your technical plan.
''',

    "Work Plan and Timeline": '''
## WORK PLAN: PROVING EXECUTABILITY
This proves you've thought through the actual execution.
''',

    "Key Personnel Biographical Sketches": '''
## BIOGRAPHICAL SKETCHES: PROVING TEAM CAPABILITY
Reviewers need to believe your team can execute.
''',

    "Facilities, Equipment, and Other Resources": '''
## FACILITIES & EQUIPMENT: PROVING INFRASTRUCTURE
Reviewers want to know you can actually do the work.
'''
}


class GrantAgent:
    """AI agent for generating grant proposal sections using expert-level prompts"""

    def __init__(self, cost_tracker: CostTracker, agency_loader: AgencyLoader):
        # Configure Anthropic client for Replit AI Integrations
        api_key = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL")

        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )
        self.cost_tracker = cost_tracker
        self.model = Config.MODEL
        self.agency_loader = agency_loader

        # Load company context from file or accept as parameter
        company_context_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "company_context.json")
        if os.path.exists(company_context_path):
            with open(company_context_path, "r") as f:
                data = json.load(f)
                self.company_context = CompanyContext(**data)
        else:
            self.company_context = CompanyContext(
                company_name="",
                founded="",
                location="",
                industry="",
                focus_area="",
                mission="",
                problem_statement="",
                solution="",
                team=[]
            )

        # Generate agency-specific requirements text
        self.agency_requirements = self.agency_loader.generate_requirements_text()

        # Get section guidelines
        self.section_guidelines = self.agency_loader.get_section_guidelines()

        # Get agency name for prompt selection
        self.agency_name = self.agency_loader.requirements.agency

    def _get_expert_system_prompt(self, prompt_type: str) -> str:
        """Get the expert system prompt for the current agency and prompt type"""
        agency_prompts = EXPERT_SYSTEM_PROMPTS.get(self.agency_name, EXPERT_SYSTEM_PROMPTS["NSF"])
        base_prompt = agency_prompts.get(prompt_type, "")
        return base_prompt.format(agency_requirements=self.agency_requirements)

    def _get_section_guidance(self, section_name: str) -> str:
        """Get expert guidance for a specific section type"""
        # Map section names to guidance keys — try exact match first
        if section_name in SECTION_EXPERT_GUIDANCE:
            return SECTION_EXPERT_GUIDANCE[section_name]

        # Fall back to fuzzy mapping for multi-agency section names
        section_mapping = {
            "Technical Abstract": "Technology Innovation",
            "Phase I Technical Objectives": "Technical Objectives and Challenges",
            "Innovation and Technical Approach": "Technical Objectives and Challenges",
            "Broader Impacts": "Broader Impacts",
            "Anticipated Benefits": "Broader Impacts",
            "Commercialization Plan": "Commercialization Plan",
            "Commercialization Strategy": "Commercialization Plan",
            "Dual Use and Commercialization": "Commercialization Plan",
            "Budget and Budget Justification": "Budget and Budget Justification",
            "Budget Narrative and Justification": "Budget and Budget Justification",
            "Cost Proposal and Budget Justification": "Budget and Budget Justification",
            "Work Plan and Timeline": "Work Plan and Timeline",
            "Work Plan": "Work Plan and Timeline",
            "Key Personnel Biographical Sketches": "Key Personnel Biographical Sketches",
            "Key Personnel": "Key Personnel Biographical Sketches",
            "Key Personnel and Qualifications": "Key Personnel Biographical Sketches",
            "Facilities, Equipment, and Other Resources": "Facilities, Equipment, and Other Resources",
            "Facilities and Equipment": "Facilities, Equipment, and Other Resources",
            "Company Capabilities and Experience": "Facilities, Equipment, and Other Resources",
        }

        guidance_key = section_mapping.get(section_name)
        if guidance_key:
            return SECTION_EXPERT_GUIDANCE.get(guidance_key, "")
        return ""

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
        """Generate initial draft of a grant section using expert prompts"""
        console.print(f"\n[bold blue]📝 Generating {section_name}...[/bold blue]")

        # Get agency info
        agency_info = self.agency_loader.requirements
        funding_amount = self.agency_loader.get_funding_amount()
        duration_months = self.agency_loader.get_duration_months()

        # Check for character limit on this section
        char_limit = 0
        for _key, sec in self.agency_loader.get_sections().items():
            if sec.name == section_name:
                char_limit = sec.max_chars
                break

        # Get expert system prompt for this agency
        system_prompt = self._get_expert_system_prompt("generate")

        # Get section-specific expert guidance
        section_guidance = self._get_section_guidance(section_name)

        company_json = self.company_context.model_dump_json(indent=2)

        # Build length constraint
        if char_limit > 0:
            length_instruction = (
                f"- HARD CHARACTER LIMIT: {char_limit:,} characters maximum (including spaces)\n"
                f"- Count your characters carefully. Content that exceeds {char_limit:,} characters will be truncated.\n"
                f"- Target approximately {char_limit - 200:,} to {char_limit:,} characters to use the space fully without going over."
            )
        else:
            length_instruction = f"- Target length: {target_length}"

        user_prompt = f"""Generate the "{section_name}" section for a {agency_info.agency} {agency_info.program} grant proposal.

## SECTION REQUIREMENTS
{length_instruction}
- Funding: ${funding_amount:,} over {duration_months} months
- This is Phase I: Focus on FEASIBILITY DEMONSTRATION

## CRITICAL RULES
- Do NOT fabricate technical claims, performance numbers, hypotheses, or test results
- Do NOT invent team credentials, publications, or prior grants
- Use ONLY information from the company context provided below
- If data is missing, state what exists rather than inventing what doesn't

## SECTION-SPECIFIC EXPERT GUIDANCE
{section_guidance}

## AGENCY GUIDELINES FOR THIS SECTION
{self.section_guidelines.get(section_name, "")}

## COMPANY INFORMATION
{company_json}

## YOUR TASK
Write this section to score "Excellent" by:
1. Opening with the most compelling point — reviewers decide quickly
2. Using specific, evidence-based claims from the company context
3. Structuring content for easy scanning by busy reviewers
4. Maintaining appropriate scope for Phase I feasibility
5. Staying strictly within the character/length limit

Generate the complete {section_name} section now. Write in a professional, compelling style. Output ONLY the section text — no headers, labels, or meta-commentary:"""

        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            task = progress.add_task(f"Calling Claude for {section_name}...", total=None)
            content, input_tokens, output_tokens = self._call_claude(system_prompt, user_prompt, max_tokens=Config.MAX_TOKENS_GENERATE)

        # Track cost
        self.cost_tracker.record_usage(section_name, "generate", input_tokens, output_tokens, self.model)

        # Enforce character limit — hard truncate at sentence boundary if exceeded
        if char_limit > 0 and len(content) > char_limit:
            truncated = content[:char_limit]
            last_period = truncated.rfind('.')
            if last_period > char_limit * 0.8:
                content = truncated[:last_period + 1]
            else:
                content = truncated
            console.print(f"[yellow]⚠ Truncated to {len(content)} chars (limit: {char_limit})[/yellow]")

        word_count = len(content.split())
        char_count = len(content)
        console.print(f"[green]✓ Generated {word_count} words, {char_count} chars[/green]")

        return GrantSection(
            name=section_name,
            content=content,
            word_count=word_count,
            char_count=char_count,
            iteration=0
        )

    def critique_section(self, section: GrantSection) -> str:
        """Generate critical feedback using expert reviewer perspective"""
        console.print(f"[bold yellow]🔍 Critiquing {section.name}...[/bold yellow]")

        agency_info = self.agency_loader.requirements

        # Get expert critique prompt for this agency
        system_prompt = self._get_expert_system_prompt("critique")

        # Get section-specific guidance for the critique
        section_guidance = self._get_section_guidance(section.name)

        user_prompt = f"""Conduct a rigorous review of this {agency_info.agency} {agency_info.program} proposal section as if you were on the review panel.

## SECTION BEING REVIEWED: {section.name}

## EXPERT GUIDANCE FOR THIS SECTION TYPE
{section_guidance}

## CURRENT DRAFT
{section.content}

## YOUR REVIEW TASK
Provide a thorough critique that identifies:

1. **OVERALL RATING**: Would you rate this "Poor," "Fair," "Good," "Very Good," or "Excellent"? Why?

2. **BIGGEST WEAKNESS**: What is the single most important issue that could hurt the score?

3. **MISSING ELEMENTS**: What required elements are absent or insufficient?

4. **WEAK CLAIMS**: Which statements lack evidence or supporting data?

5. **SCOPE ISSUES**: Is the scope appropriate for Phase I? Too broad? Too narrow?

6. **STRUCTURAL PROBLEMS**: Does the organization help or hurt reviewer comprehension?

7. **LANGUAGE ISSUES**: Any vague, generic, or problematic language?

8. **SPECIFIC IMPROVEMENTS**: What exact changes would elevate this to "Excellent"?

Be demanding. A harsh internal critique prevents rejection by the real reviewers. Provide specific, actionable feedback:"""

        critique, input_tokens, output_tokens = self._call_claude(system_prompt, user_prompt, max_tokens=Config.MAX_TOKENS_CRITIQUE)

        self.cost_tracker.record_usage(section.name, "critique", input_tokens, output_tokens, self.model)

        console.print(f"[green]✓ Critique complete[/green]")
        return critique

    def refine_section(self, section: GrantSection, critique: str) -> GrantSection:
        """Refine section based on critique to achieve top scores"""
        console.print(f"[bold cyan]✨ Refining {section.name}...[/bold cyan]")

        agency_info = self.agency_loader.requirements

        # Get expert refinement prompt for this agency
        system_prompt = self._get_expert_system_prompt("refine")

        # Get section-specific guidance
        section_guidance = self._get_section_guidance(section.name)

        user_prompt = f"""Revise this {agency_info.agency} {agency_info.program} proposal section to address ALL critique points and achieve an "Excellent" rating.

## SECTION: {section.name}

## EXPERT GUIDANCE FOR THIS SECTION TYPE
{section_guidance}

## CURRENT DRAFT
{section.content}

## CRITIQUE TO ADDRESS
{critique}

## REVISION REQUIREMENTS
1. **Address every critique point** - Don't leave any weakness unresolved
2. **Strengthen all claims with evidence** - Add citations, data, or logical derivations
3. **Improve specificity** - Replace vague language with concrete details
4. **Enhance structure** - Make it easy for reviewers to find key points
5. **Maintain scope** - Keep within Phase I boundaries
6. **Stay within length limits** - Similar length to original

## LANGUAGE TRANSFORMATIONS TO APPLY
- "We believe X" → "Evidence demonstrates X [with citation or data]"
- "Significant improvement" → "[Quantified]x improvement in [specific metric]"
- "Large market" → "$[X]M market based on [specific analysis]"
- "Will benefit [group]" → "Will [specific benefit] for [quantified population]"

Generate the improved version that would score "Excellent" from even demanding reviewers:"""

        refined_content, input_tokens, output_tokens = self._call_claude(system_prompt, user_prompt, max_tokens=Config.MAX_TOKENS_REFINE)

        self.cost_tracker.record_usage(section.name, "refine", input_tokens, output_tokens, self.model)

        word_count = len(refined_content.split())
        console.print(f"[green]✓ Refined to {word_count} words[/green]")

        return GrantSection(
            name=section.name,
            content=refined_content,
            word_count=word_count,
            iteration=section.iteration + 1,
            critique=critique,
            refinement_notes="Refined based on expert-level critical feedback"
        )
