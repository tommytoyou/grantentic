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


def generate_blueprint_content(
    company_name: str,
    technology: str,
    problem: str,
    agency: str,
    differentiator: str,
) -> str:
    """Call Claude to generate personalized SBIR Blueprint content."""

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

    system_prompt = f"""You are an expert SBIR grant consultant who has helped 200+ companies
secure Phase I funding. You produce personalized, actionable section-by-section guidance
for {agency_name} {program} proposals.

CRITICAL RULES:
- Every recommendation must be specific to the company's technology — no generic advice
- Do NOT fabricate technical claims, numbers, or performance data
- Reference what the reviewer is looking for in each section
- Keep guidance concrete: "Write about X" not "Consider mentioning something"
- Use the company's own language from their intake form"""

    user_prompt = f"""Create a personalized SBIR Blueprint for this company applying to {agency_name} {program}.

## COMPANY INTAKE
- Company Name: {company_name}
- Technology: {technology}
- Problem Being Solved: {problem}
- Innovation Differentiator: {differentiator}

## AGENCY SECTION REQUIREMENTS
{sections_text}

## YOUR TASK
For EACH section required by {agency_name}, produce:

1. **Section Title** and character/word limit
2. **What the reviewer wants to see** — specific to this agency
3. **Your recommended approach** — personalized to this company's technology
4. **Opening sentence suggestion** — a strong first sentence tailored to their innovation
5. **Key points to include** — 3-5 bullet points specific to their technology/problem
6. **What to avoid** — common mistakes for this section

Also include:
- A one-paragraph "Elevator Pitch" summary the company can use verbatim
- 2-3 suggested measurable Phase I objectives based on their technology
- Competitive positioning advice based on their differentiator

Format with clear markdown headers for each section. Be specific and actionable."""

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
