# Grantentic - AI-Powered Grant Writing System

## Project Overview
An agentic AI-powered grant writing system for space startups using Python and Anthropic's Claude Sonnet 4. Generates NSF SBIR Phase I grant proposals through an iterative generate → critique → refine workflow.

## Architecture
- **Agent-based system**: Uses Claude Sonnet 4 for intelligent grant generation
- **Iterative refinement**: Each section goes through generate, self-critique, and refine cycles
- **Quality validation**: Automated checking against NSF SBIR requirements
- **Cost optimization**: Tracks token usage to stay within $2-5 per grant target

## Tech Stack
- Python 3.11
- Anthropic Claude API (via Replit AI Integrations - no API key required)
- python-docx for Word export
- Pydantic for data validation
- Rich for CLI output
- tiktoken for cost tracking

## Project Structure
```
/
├── main.py                           # CLI entry point
├── src/
│   ├── models.py                     # Pydantic data models
│   ├── cost_tracker.py               # API cost tracking
│   ├── grant_agent.py                # Core AI agent
│   ├── agentic_workflow.py           # Generate/critique/refine workflow
│   ├── quality_checker.py            # NSF requirements validation
│   └── docx_exporter.py              # Word document export
├── data/
│   ├── company_context.json          # Deep Space Dynamics info
│   └── nsf_sbir_requirements.txt     # NSF evaluation criteria
└── outputs/                          # Generated grant proposals (.docx)
```

## Recent Changes
- 2025-11-16: Initial project setup
- Created complete agentic grant writing system with all components
- Configured Deep Space Dynamics as first customer (CubeSat asteroid detection startup)
- Set up NSF SBIR Phase I requirements and evaluation criteria

## Features Implemented
1. ✅ Anthropic Claude Sonnet 4 integration via Replit AI Integrations
2. ✅ Agentic workflow: generate → self-critique → refine
3. ✅ NSF SBIR Phase I grant generator (4 sections)
4. ✅ Quality validation against NSF requirements
5. ✅ Company context loader (Deep Space Dynamics)
6. ✅ NSF requirements parser
7. ✅ Word document (.docx) export
8. ✅ Cost tracking system ($2-5 target)
9. ✅ Main CLI entry point
10. ✅ Rich console logging

## Usage
```bash
python main.py
```

Generates complete NSF SBIR Phase I proposal for Deep Space Dynamics including:
- Project Pitch (1-2 pages)
- Technical Objectives (5-6 pages)
- Broader Impacts (1-2 pages)
- Commercialization Plan (2-3 pages)

## First Customer
**Deep Space Dynamics** - Boulder, CO aerospace startup developing CubeSat constellations for asteroid detection and planetary defense. Seeking NSF SBIR Phase I funding ($275K) for flight-ready optical payload development.

## Cost Optimization
- Target: $2-5 per grant
- Model: Claude Sonnet 4
- Real-time token tracking with tiktoken
- Detailed cost reporting per section and operation

## Outputs
Word documents saved to `outputs/` with timestamp:
- Deep_Space_Dynamics_NSF_SBIR_Phase1_[timestamp].docx
