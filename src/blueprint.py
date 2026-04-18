"""
SBIR Blueprint Generator
Generates a personalized SBIR section breakdown using Claude API
and produces PDF output for email delivery.
"""

import io
import json
import logging
import os
from pathlib import Path
from datetime import datetime

import anthropic
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
)

from config import Config
from src.agency_loader import load_agency_requirements

log = logging.getLogger("grantentic.blueprint")

PRIMARY_COLOR = HexColor("#0284c7")
DARK_COLOR = HexColor("#1e293b")
GRAY_COLOR = HexColor("#64748b")


def generate_blueprint_content(intake: dict, agency: str) -> str:
    """Call Claude to generate personalized SBIR Blueprint from 13-field intake."""

    # Load agency requirements
    try:
        loader = load_agency_requirements(agency)
        sections_text = ""
        for _key, sec in loader.get_ordered_sections():
            limit = f"{sec.max_chars:,} characters" if sec.max_chars else f"{sec.min_words}-{sec.max_words} words"
            sections_text += f"\n### {sec.name} ({limit})\n{sec.guidelines}\n"
        agency_name = loader.requirements.agency
        program = loader.requirements.program
    except Exception:
        sections_text = ""
        agency_name = agency.upper()
        program = "SBIR Phase I"

    # Agency-specific emphasis instructions
    agency_emphasis = {
        "nsf": (
            "This is an NSF proposal. NSF weights Intellectual Merit at 50% of the score. "
            "The Problem section is the single most important section — it must establish "
            "scientific significance, not just commercial need. Emphasize what new knowledge "
            "this research will create, why existing scientific understanding is insufficient, "
            "and what testable hypothesis the applicant is proposing. Broader Impacts (societal "
            "benefit beyond commercial value) also matters — weave it into guidance where relevant.\n\n"
            "CRITICAL NSF REFRAMING RULE: Before writing any section, identify the novel "
            "knowledge, validated models, algorithms, datasets, or engineering frameworks that "
            "will be produced by this Phase I work that do not currently exist in the literature. "
            "These knowledge outputs are the fundable scientific contribution. The hardware, "
            "components, and integration work are the research instrument, not the research. "
            "Never lead with components, integration, or assembly. Always lead with what will "
            "be known or validated after Phase I that is not known now. Reframe every technical "
            "objective as a knowledge generation activity."
        ),
        "dod": (
            "This is a DoD proposal. DoD weights Technical Merit at 40% and Military Relevance "
            "at 30%. The Technical Approach must show a clear TRL advancement plan with specific "
            "performance targets. Military Relevance must connect to a named capability gap, "
            "program, or mission — generic statements like 'helps the warfighter' score poorly. "
            "Transition potential (how this reaches operational use) is critical. Use DoD "
            "terminology: TRL, SWaP-C, CONOPS, PEO, Phase III transition."
        ),
        "nasa": (
            "This is a NASA proposal. NASA weights Technical Merit and NASA Mission Alignment "
            "equally at 35% each. The technical approach must advance state-of-the-art with "
            "quantified improvement. Mission alignment must reference specific NASA Technology "
            "Taxonomy areas, named missions or programs, and NASA centers. Space environment "
            "constraints (radiation, thermal, vacuum) should be addressed if applicable. "
            "Dual-use applications (NASA + commercial space + terrestrial) strengthen the "
            "commercialization section."
        ),
    }

    system_prompt = f"""You are an expert SBIR grant consultant who has helped 200+ companies
secure Phase I funding. You produce personalized, actionable section-by-section guidance
for {agency_name} {program} proposals.

## AGENCY EMPHASIS
{agency_emphasis.get(agency.lower(), agency_emphasis["nsf"])}

## CRITICAL RULES

### What you MUST do:
- Make every recommendation specific to THIS company's technology, problem, and team
- Use the applicant's own words and data from their intake — quote them, reference their
  specific competitors by name, cite their PI's actual credentials
- When the applicant provided optional fields (market size, team members, prior work,
  solicitation number), incorporate them directly into the relevant section guidance
- When optional fields are empty, skip them entirely — do not mention them or leave
  placeholder text like "[if available]"
- Structure output in exactly 4 sections matching the agency's section format

### What you must NEVER do:
- Fabricate technical claims, performance numbers, test results, or statistics
- Invent team credentials, publications, patents, or prior grants
- Add information the applicant did not provide — if their intake is thin on a point,
  tell them what they need to add, do not make it up for them
- Give generic grant writing advice — every sentence must be specific to this company

### Red flag detection:
Before producing the Blueprint, analyze the applicant's problem statement for these
top rejection patterns. If you detect any, include a "WARNING" callout at the top of
the Blueprint explaining the risk and how to fix it:
- Systems integration without a testable hypothesis (building a platform vs. proving
  a scientific/technical question)
- Incremental improvement without genuine novelty (making something faster/cheaper
  without a new technical approach)
- Product development scope rather than feasibility demonstration (building a product
  vs. answering "can this work?")
- Missing quantification of the problem (no numbers showing severity or scale)"""

    # ── Build intake sections, including optional fields only when present ──

    # Section 1: always present (all required)
    s1_block = f"""## APPLICANT INTAKE — SECTION 1: THE PROBLEM
- Company Name: {intake.get('company_name', '')}
- Problem Being Solved: {intake.get('problem', '')}
- Who Suffers and How Severely: {intake.get('who_suffers', '')}
- Why Current Solutions Fail: {intake.get('why_current_fail', '')}"""

    # Section 2: always present (all required)
    dev_stage_labels = {
        "idea": "Idea stage (no implementation yet)",
        "proof_of_concept": "Proof of Concept completed",
        "prototype": "Working Prototype built",
        "lab_tested": "Lab Tested with results",
        "field_tested": "Field Tested in real environment",
    }
    dev_stage_display = dev_stage_labels.get(
        intake.get("dev_stage", ""), intake.get("dev_stage", "")
    )
    s2_block = f"""## APPLICANT INTAKE — SECTION 2: TECHNICAL APPROACH
- Technical Approach / Innovation: {intake.get('technology', '')}
- Current Development Stage: {dev_stage_display}
- What Phase I Will Produce or Demonstrate: {intake.get('phase1_output', '')}"""

    # Section 3: competitors and differentiator are required, market_size is optional
    s3_lines = [
        "## APPLICANT INTAKE — SECTION 3: COMPETITIVE LANDSCAPE",
        f"- Named Competitors and Their Limitations: {intake.get('competitors', '')}",
        f"- Key Technical Differentiator: {intake.get('differentiator', '')}",
    ]
    if intake.get("market_size"):
        s3_lines.append(f"- Target Market and Estimated Size: {intake['market_size']}")
    s3_block = "\n".join(s3_lines)

    # Section 4: PI is required, rest optional
    s4_lines = [
        "## APPLICANT INTAKE — SECTION 4: TEAM",
        f"- Principal Investigator: {intake.get('pi_background', '')}",
    ]
    if intake.get("team_members"):
        s4_lines.append(f"- Other Key Team Members: {intake['team_members']}")
    if intake.get("prior_work"):
        s4_lines.append(f"- Prior Grants, Publications, or Patents: {intake['prior_work']}")
    if intake.get("solicitation"):
        s4_lines.append(f"- Target Solicitation / Topic Number: {intake['solicitation']}")
    s4_block = "\n".join(s4_lines)

    # ── Solicitation-specific instruction (only if provided) ──
    solicitation_instruction = ""
    if intake.get("solicitation"):
        solicitation_instruction = f"""
## SOLICITATION ALIGNMENT
The applicant is targeting solicitation/topic: {intake['solicitation']}
In EVERY section of the Blueprint, explain how to align language and framing with this
specific topic area. Reference the solicitation number explicitly in your recommended
opening sentences and key points. If you recognize the topic area, note which keywords
and evaluation emphases are associated with it."""

    user_prompt = f"""Create a personalized SBIR Blueprint for {intake.get('company_name', 'this company')} applying to {agency_name} {program}.

{s1_block}

{s2_block}

{s3_block}

{s4_block}
{solicitation_instruction}

## AGENCY SECTION REQUIREMENTS
{sections_text}

## OUTPUT FORMAT

Produce the Blueprint in this exact structure:

### WARNINGS (only if red flags detected)
If the problem statement shows signs of systems integration, incremental development,
missing hypothesis, or product-development scope, lead with a clearly labeled WARNING
explaining the specific risk and concrete steps to fix it. If no red flags, skip this
section entirely.

### ELEVATOR PITCH
Write a one-paragraph pitch (4-6 sentences) this company can use verbatim. Build it
from their problem statement, who suffers, their differentiator, and their PI's
credentials. Do not add claims they did not make.

### SECTION 1: [Agency-specific section name]
- **Character/word limit:** [from agency requirements]
- **What the {agency_name} reviewer wants:** 2-3 sentences on what scores "Excellent"
- **Your recommended approach:** A specific paragraph telling this company exactly what
  to write, referencing their problem statement, their data on who suffers, and why
  current solutions fail — using their words
- **Suggested opening sentence:** One strong first sentence built from their intake data
- **Key points to hit:** 3-5 bullets drawn directly from their intake answers
- **What to avoid:** 1-2 specific pitfalls relevant to their situation

### SECTION 2: [Agency-specific section name]
Same structure. Reference their technical approach, development stage, and Phase I
deliverable. Frame Phase I objectives around their stated output.

### SECTION 3: [Agency-specific section name]
Same structure. Name the specific competitors they listed. Position their differentiator
against those competitors' stated limitations.{' Include their market size data.' if intake.get('market_size') else ''}

### SECTION 4: [Agency-specific section name]
Same structure. Use the PI's actual name and background.{' Reference their other team members by name and role.' if intake.get('team_members') else ''}{' Cite their specific prior grants, publications, or patents.' if intake.get('prior_work') else ''}

### SUGGESTED PHASE I OBJECTIVES
2-3 measurable objectives derived from their stated Phase I deliverable
("{intake.get('phase1_output', '')}") and their current development stage
({dev_stage_display}). Each objective must have a quantifiable success criterion.

### COMPETITIVE POSITIONING STRATEGY
Using the specific competitors they named ({intake.get('competitors', '')[:200]}...)
and their stated differentiator, provide 3-4 sentences of positioning advice they
can weave throughout the proposal.

Be specific. Be actionable. Every sentence must reference this company's actual situation."""

    client = anthropic.Anthropic(
        api_key=os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("AI_INTEGRATIONS_ANTHROPIC_BASE_URL"),
    )

    response = client.messages.create(
        model=Config.MODEL,
        max_tokens=6000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])
    log.info(
        "blueprint: generated %d chars, %d input / %d output tokens",
        len(content), response.usage.input_tokens, response.usage.output_tokens,
    )
    return content


def _build_pdf_styles():
    """Create custom paragraph styles for the Blueprint PDF."""
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "BlueprintTitle",
        parent=styles["Title"],
        fontSize=24,
        textColor=PRIMARY_COLOR,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "BlueprintSubtitle",
        parent=styles["Normal"],
        fontSize=12,
        textColor=GRAY_COLOR,
        spaceAfter=24,
    ))
    styles.add(ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=DARK_COLOR,
        spaceBefore=18,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=6,
    ))
    return styles


def _markdown_to_paragraphs(text: str, styles) -> list:
    """Convert markdown-ish text to reportlab paragraphs."""
    elements = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            elements.append(Spacer(1, 6))
        elif stripped.startswith("# "):
            elements.append(Paragraph(stripped[2:], styles["SectionHead"]))
        elif stripped.startswith("## "):
            elements.append(Paragraph(stripped[3:], styles["SectionHead"]))
        elif stripped.startswith("### "):
            elements.append(Paragraph(f"<b>{stripped[4:]}</b>", styles["Body"]))
        elif stripped.startswith("**") and stripped.endswith("**"):
            elements.append(Paragraph(f"<b>{stripped[2:-2]}</b>", styles["Body"]))
        elif stripped.startswith("- ") or stripped.startswith("* "):
            bullet_text = stripped[2:]
            # Handle **bold** within bullets
            bullet_text = bullet_text.replace("**", "<b>", 1).replace("**", "</b>", 1)
            elements.append(Paragraph(f"&bull; {bullet_text}", styles["Body"]))
        else:
            # Handle inline **bold**
            import re
            cleaned = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', stripped)
            elements.append(Paragraph(cleaned, styles["Body"]))
    return elements


def create_blueprint_pdf(
    company_name: str,
    agency: str,
    content: str,
) -> bytes:
    """Generate the personalized Blueprint PDF and return as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = _build_pdf_styles()
    elements = []

    # Title page
    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph("SBIR Blueprint", styles["BlueprintTitle"]))
    elements.append(Paragraph(
        f"Personalized for {company_name} | {agency.upper()} SBIR Phase I",
        styles["BlueprintSubtitle"],
    ))
    elements.append(Paragraph(
        f"Generated {datetime.now().strftime('%B %d, %Y')} by Grantentic",
        styles["BlueprintSubtitle"],
    ))
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "This document contains a personalized section-by-section strategy "
        "for your SBIR Phase I submission. Each section includes what the "
        "reviewer is looking for, recommended approach, and specific guidance "
        "based on your technology.",
        styles["Body"],
    ))
    elements.append(PageBreak())

    # Content
    elements.extend(_markdown_to_paragraphs(content, styles))

    # Footer note
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "<i>This Blueprint was generated by Grantentic's AI system and should be "
        "reviewed and adapted by the applicant. Grantentic does not guarantee "
        "funding outcomes.</i>",
        styles["Body"],
    ))

    doc.build(elements)
    return buf.getvalue()


def create_prompt_pack_pdf(agency: str) -> bytes:
    """Generate the SBIR Prompt Pack PDF — reusable Claude prompts."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = _build_pdf_styles()
    elements = []

    elements.append(Spacer(1, 1.5 * inch))
    elements.append(Paragraph("SBIR Prompt Pack", styles["BlueprintTitle"]))
    elements.append(Paragraph(
        f"{agency.upper()} SBIR Phase I | Ready-to-use AI Prompts",
        styles["BlueprintSubtitle"],
    ))
    elements.append(PageBreak())

    # Load agency sections for prompt generation
    try:
        loader = load_agency_requirements(agency)
        ordered = loader.get_ordered_sections()
    except Exception:
        ordered = []

    elements.append(Paragraph("How to Use These Prompts", styles["SectionHead"]))
    elements.append(Paragraph(
        "Copy each prompt below into Claude (claude.ai) or ChatGPT. Replace the "
        "[bracketed placeholders] with your company's specific information. "
        "Each prompt is designed to produce content that matches what reviewers "
        "look for in that section.",
        styles["Body"],
    ))
    elements.append(Spacer(1, 12))

    for _key, sec in ordered:
        limit = f"{sec.max_chars:,} characters" if sec.max_chars else f"{sec.min_words}-{sec.max_words} words"
        elements.append(Paragraph(f"Prompt: {sec.name}", styles["SectionHead"]))
        elements.append(Paragraph(f"<i>Limit: {limit}</i>", styles["Body"]))

        prompt_text = (
            f"Write the \"{sec.name}\" section for an {agency.upper()} SBIR Phase I "
            f"proposal. My company [COMPANY NAME] is developing [TECHNOLOGY DESCRIPTION] "
            f"to solve [PROBLEM]. Our key innovation is [DIFFERENTIATOR]. "
            f"Keep the output under {limit}. "
            f"The reviewer is looking for: {sec.description}. "
            f"Start with a strong opening sentence that quantifies the problem."
        )
        elements.append(Paragraph(
            f'<font face="Courier" size="9">{prompt_text}</font>',
            styles["Body"],
        ))
        elements.append(Spacer(1, 12))

    elements.append(Spacer(1, 0.5 * inch))
    elements.append(Paragraph(
        "<i>These prompts are provided by Grantentic as a starting point. "
        "Always review and refine AI-generated content before submission.</i>",
        styles["Body"],
    ))

    doc.build(elements)
    return buf.getvalue()


def send_blueprint_email(
    to_email: str,
    company_name: str,
    agency: str,
    blueprint_pdf: bytes,
    prompt_pack_pdf: bytes,
) -> bool:
    """Send the Blueprint and Prompt Pack PDFs via Resend."""
    import base64

    resend_key = Config.RESEND_API_KEY
    if not resend_key:
        log.warning("send_blueprint_email: RESEND_API_KEY not set, skipping")
        return False

    import resend
    resend.api_key = resend_key

    try:
        resend.Emails.send({
            "from": "Grantentic <noreply@grantentic.us>",
            "to": [to_email],
            "subject": f"Your SBIR Blueprint for {company_name} is ready",
            "html": (
                f"<p>Hi,</p>"
                f"<p>Your personalized {agency.upper()} SBIR Blueprint for "
                f"<strong>{company_name}</strong> is attached.</p>"
                f"<p>You'll find two PDFs:</p>"
                f"<ul>"
                f"<li><strong>SBIR Blueprint</strong> — your personalized section-by-section "
                f"strategy with specific guidance for your technology</li>"
                f"<li><strong>SBIR Prompt Pack</strong> — ready-to-use AI prompts you can "
                f"paste into Claude or ChatGPT to draft each section</li>"
                f"</ul>"
                f"<p>Ready for the full proposal? You have a <strong>$29 credit</strong> "
                f"toward Grantentic's AI-powered proposal generation.</p>"
                f'<p><a href="https://www.grantentic.us/generate">Generate Your Full Proposal</a></p>'
                f"<p>Good luck with your submission!</p>"
                f"<p>— The Grantentic Team</p>"
            ),
            "attachments": [
                {
                    "filename": f"SBIR_Blueprint_{company_name.replace(' ', '_')}.pdf",
                    "content": base64.b64encode(blueprint_pdf).decode(),
                    "type": "application/pdf",
                },
                {
                    "filename": f"SBIR_Prompt_Pack_{agency.upper()}.pdf",
                    "content": base64.b64encode(prompt_pack_pdf).decode(),
                    "type": "application/pdf",
                },
            ],
        })
        log.info("send_blueprint_email: sent to %s", to_email)
        return True
    except Exception as exc:
        log.exception("send_blueprint_email: failed: %s", exc)
        return False
