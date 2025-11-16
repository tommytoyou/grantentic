# Grantentic 🚀

An agentic AI-powered grant writing system for space startups using Python and Anthropic's Claude API.

## Overview

Grantentic automates the creation of NSF SBIR Phase I grant proposals using an advanced agentic workflow that generates, critiques, and refines each section for maximum quality.

## Features

- **Agentic Workflow**: Generate → Self-Critique → Refine process for each section
- **Claude Sonnet 4 Integration**: Powered by Anthropic's latest AI model
- **NSF SBIR Phase I**: Specialized for NSF Small Business Innovation Research proposals
- **Quality Validation**: Automated checks against NSF requirements
- **Cost Tracking**: Monitor API usage to stay within $2-5 per grant target
- **Word Export**: Professional .docx output ready for submission

## Architecture

### Core Components

1. **Grant Agent** (`src/grant_agent.py`): AI agent for generating grant sections
2. **Agentic Workflow** (`src/agentic_workflow.py`): Orchestrates the iterative refinement process
3. **Quality Checker** (`src/quality_checker.py`): Validates against NSF requirements
4. **Cost Tracker** (`src/cost_tracker.py`): Monitors token usage and API costs
5. **DOCX Exporter** (`src/docx_exporter.py`): Creates formatted Word documents

### Grant Sections

Each NSF SBIR Phase I proposal includes:

1. **Project Pitch** (1-2 pages): Problem, solution, innovation, market
2. **Technical Objectives** (5-6 pages): Methodology, risks, milestones
3. **Broader Impacts** (1-2 pages): Societal benefits, diversity
4. **Commercialization Plan** (2-3 pages): Market, customers, business model

## Usage

Run the grant generation system:

```bash
python main.py
```

The system will:
1. Load company context from `data/company_context.json`
2. Load NSF requirements from `data/nsf_sbir_requirements.txt`
3. Generate all four sections using agentic workflow
4. Validate quality against NSF criteria
5. Export to Word document in `outputs/`
6. Display cost summary and metrics

## Data Files

### Company Context (`data/company_context.json`)

Contains comprehensive information about the company:
- Company background and team
- Technology and innovation details
- Market opportunity
- Current progress and milestones
- Funding needs

### NSF Requirements (`data/nsf_sbir_requirements.txt`)

Contains NSF SBIR Phase I evaluation criteria:
- Intellectual merit
- Broader impacts
- Commercial impact
- Quality standards

## First Customer

**Deep Space Dynamics** - A Boulder-based aerospace startup developing CubeSat constellations for asteroid detection and planetary defense. Applying for NSF SBIR Phase I funding ($275K) to complete flight-ready optical payload development.

## Cost Optimization

- Target: $2-5 per grant
- Tracking: Real-time token counting and cost calculation
- Model: Claude Sonnet 4 (efficient and high-quality)
- Pricing: ~$3 per million input tokens, ~$15 per million output tokens

## Output

Generated grants are saved to `outputs/` as:
```
Deep_Space_Dynamics_NSF_SBIR_Phase1_[timestamp].docx
```

Includes:
- Professional formatting
- Table of contents
- All four required sections
- Metadata footer with word count and cost

## Technology Stack

- **Python 3.11**
- **Anthropic Claude API** (via Replit AI Integrations)
- **python-docx**: Word document generation
- **Pydantic**: Data validation
- **Rich**: Beautiful CLI output
- **tiktoken**: Token counting

## System Requirements

- Python 3.11+
- Anthropic API access (via Replit AI Integrations)
- All dependencies installed via `pyproject.toml`

---

Built with ❤️ for space startups advancing humanity's future
