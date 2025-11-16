# Multi-Agency Grant Support

Grantentic now supports multiple funding agencies with agency-specific requirements, evaluation criteria, and formatting guidelines.

## Supported Agencies

### 1. NSF (National Science Foundation) SBIR Phase I
- **Funding:** $275,000
- **Duration:** 6 months
- **Focus:** Scientific innovation and broader societal impacts
- **Sections:** 8 required sections

### 2. DoD (Department of Defense) SBIR Phase I
- **Funding:** $200,000
- **Duration:** 6 months
- **Focus:** Military applications and dual-use technology
- **Applicable to:** Air Force, Space Force, and other DoD branches
- **Sections:** 9 required sections

### 3. NASA SBIR Phase I
- **Funding:** $150,000
- **Duration:** 6 months
- **Focus:** Space applications and technology advancement
- **Sections:** 9 required sections

## Selecting an Agency

### Method 1: Environment Variable (Recommended)

```bash
# Set agency before running
export GRANT_AGENCY=nsf   # Options: nsf, dod, nasa
python main.py
```

### Method 2: Edit config.py

```python
# In config.py
class Config:
    AGENCY = 'dod'  # Change to: nsf, dod, or nasa
```

### Method 3: Runtime Override

```bash
# One-time override
GRANT_AGENCY=nasa python main.py
```

## Agency-Specific Features

### Different Sections

Each agency requires different proposal sections:

**NSF Sections:**
1. Project Pitch
2. Technical Objectives
3. Broader Impacts
4. Commercialization Plan
5. Budget and Budget Justification
6. Work Plan and Timeline
7. Key Personnel Biographical Sketches
8. Facilities, Equipment, and Other Resources

**DoD Sections:**
1. Technical Abstract
2. Identification and Significance of Problem
3. Phase I Technical Objectives
4. Work Plan
5. Related Work
6. Dual Use and Commercialization
7. Company Capabilities and Experience
8. Key Personnel
9. Cost Proposal and Budget Justification

**NASA Sections:**
1. Technical Abstract
2. Innovation and Technical Approach
3. Anticipated Benefits
4. Work Plan
5. Related Research
6. Commercialization Strategy
7. Facilities and Equipment
8. Key Personnel and Qualifications
9. Budget Narrative and Justification

### Different Page Limits

Each agency has specific word count and page limits:

| Section Type | NSF | DoD | NASA |
|---|---|---|---|
| Abstract/Pitch | 400-800 words | 100-400 words | 200-400 words |
| Technical | 2,000-2,400 words | 1,200-1,600 words | 1,200-2,000 words |
| Budget | 800-1,200 words | 800-1,600 words | 800-1,200 words |

### Different Evaluation Criteria

**NSF Evaluation (100%):**
- Intellectual Merit: 50%
- Broader Impacts: 25%
- Commercialization Potential: 25%

**DoD Evaluation (100%):**
- Technical Merit: 40%
- DoD Relevance: 30%
- Commercialization: 20%
- Team Capability: 10%

**NASA Evaluation (100%):**
- Technical Merit: 35%
- NASA Relevance: 35%
- Commercialization: 20%
- Experience: 10%

### Different Required Keywords

Each agency requires specific terminology:

**NSF Focus:**
- Innovation, scientific knowledge, broader impacts
- TRL advancement, feasibility studies
- Societal benefits, diversity

**DoD Focus:**
- Military capability, DoD requirements
- Dual-use applications, Phase III transition
- Technical readiness, operational impact

**NASA Focus:**
- Space applications, NASA missions
- TRL advancement (typically 2→4)
- Technology taxonomy alignment

## System Architecture

### Agency Templates

Templates are stored in `agency_templates/` directory:

```
agency_templates/
├── nsf/
│   └── requirements.json
├── dod/
│   └── requirements.json
└── nasa/
    └── requirements.json
```

### Requirements File Format

Each `requirements.json` contains:

```json
{
  "agency": "NSF",
  "program": "SBIR Phase I",
  "funding_amount": 275000,
  "duration_months": 6,
  "description": "...",
  "sections": { ... },
  "evaluation_criteria": { ... },
  "format_specifications": { ... },
  "special_requirements": { ... },
  "submission_requirements": { ... }
}
```

### Agency Loader

The `AgencyLoader` class (src/agency_loader.py) handles:
- Loading agency-specific requirements
- Validating section configurations
- Providing formatted requirements text
- Generating quality check parameters

### Dynamic Section Mapping

The system dynamically maps agency sections to the standard GrantProposal model:

```python
# NSF "Project Pitch" → project_pitch
# DoD "Technical Abstract" → project_pitch
# NASA "Innovation and Technical Approach" → technical_objectives
```

This allows different agencies to use different section names while maintaining a consistent internal data structure.

## How It Works

### 1. Initialization

```python
# main.py
agency_loader = load_agency_requirements(Config.AGENCY)
agent = GrantAgent(cost_tracker, agency_loader)
workflow = AgenticWorkflow(agent, agency_loader)
quality_checker = QualityChecker(agency_loader)
```

All components receive the agency loader and adapt their behavior accordingly.

### 2. Generation

The workflow generates sections based on agency requirements:

```python
# Automatically loads agency-specific sections
sections = workflow.generate_full_proposal()
```

### 3. Quality Checking

Quality checks use agency-specific limits:

```python
# Budget validation uses agency funding amount
# Timeline checks use agency duration
# Keywords match agency requirements
quality_checker.validate_proposal(proposal, company_context)
```

### 4. Output

Generated files include agency prefix:

```
outputs/
├── Deep_Space_Dynamics_NSF_SBIR_Phase1_20250116.docx
├── Deep_Space_Dynamics_NSF_Quality_Report_20250116.md
├── Deep_Space_Dynamics_DOD_SBIR_Phase1_20250116.docx
└── Deep_Space_Dynamics_NASA_SBIR_Phase1_20250116.docx
```

## Adding New Agencies

To add support for a new agency:

### 1. Create Template File

Create `agency_templates/new_agency/requirements.json`:

```json
{
  "agency": "NEW_AGENCY",
  "program": "SBIR Phase I",
  "funding_amount": 250000,
  "duration_months": 6,
  "description": "...",
  "sections": {
    "section_key": {
      "name": "Section Name",
      "required": true,
      "min_pages": 1,
      "max_pages": 2,
      "min_words": 400,
      "max_words": 800,
      "order": 1,
      "guidelines": "...",
      "required_keywords": ["keyword1", "keyword2"],
      "description": "..."
    }
  },
  "evaluation_criteria": { ... },
  "format_specifications": { ... },
  "special_requirements": { ... },
  "submission_requirements": { ... }
}
```

### 2. Update Config

Add to `config.py`:

```python
AGENCY_PROFILES = {
    'new_agency': {
        'name': 'New Agency Name',
        'program': 'SBIR Phase I',
        'funding_amount': 250000,
        'duration_months': 6,
        'template_dir': 'new_agency',
        'description': '...'
    }
}
```

### 3. Update Section Mapping

Add section mappings in `main.py`:

```python
section_map = {
    # Existing mappings...

    # New agency sections
    "New Agency Section Name": "project_pitch",
    ...
}
```

### 4. Test

```bash
export GRANT_AGENCY=new_agency
python main.py
```

## Agency-Specific Prompts

The AI prompts automatically adapt to each agency:

**NSF Prompt Example:**
```
You are an expert grant writer specializing in NSF SBIR Phase I proposals.
Follow NSF evaluation criteria exactly...
Focus on intellectual merit and broader impacts...
```

**DoD Prompt Example:**
```
You are an expert grant writer specializing in DoD SBIR Phase I proposals.
Follow DoD evaluation criteria exactly...
Focus on military relevance and dual-use applications...
```

**NASA Prompt Example:**
```
You are an expert grant writer specializing in NASA SBIR Phase I proposals.
Follow NASA evaluation criteria exactly...
Focus on space applications and technology advancement...
```

## Best Practices

### For NSF Proposals:
1. Emphasize broader societal impacts
2. Focus on scientific advancement
3. Include diversity and inclusion efforts
4. Use accessible language for non-specialists

### For DoD Proposals:
1. Clearly identify military capability gaps
2. Emphasize dual-use applications
3. Show path to Phase III (DoD sales)
4. Reference specific DoD requirements
5. Highlight team's defense industry experience

### For NASA Proposals:
1. Align with specific NASA missions
2. Reference NASA Technology Taxonomy
3. Show TRL advancement plan
4. Identify NASA center partnerships
5. Emphasize space heritage and reliability

## Quality Checks

Agency-specific quality checks include:

1. **Budget Validation**
   - NSF: Exactly $275,000
   - DoD: Up to $200,000
   - NASA: Up to $150,000

2. **Timeline Coverage**
   - All agencies: 6-month coverage required
   - Monthly milestones expected

3. **Required Keywords**
   - Agency-specific keyword lists
   - Section-specific requirements

4. **Page Limits**
   - Agency-specific word counts
   - Auto-trimming if exceeded

5. **Format Specifications**
   - Font, spacing, margins per agency
   - Document structure requirements

## Troubleshooting

### Issue: "Unknown agency 'xyz'"
**Solution:** Check spelling and use: nsf, dod, or nasa

### Issue: "Requirements file not found"
**Solution:** Ensure `agency_templates/{agency}/requirements.json` exists

### Issue: Missing sections in output
**Solution:** Check section mapping in `main.py` - some agencies may have sections that don't map directly

### Issue: Budget validation fails
**Solution:** Ensure budget section explicitly states total matching agency funding amount

### Issue: Keywords not detected
**Solution:** Agency requirements may differ - check specific keywords in requirements.json

## Configuration Reference

### Environment Variables

```bash
# Agency selection
export GRANT_AGENCY=nsf          # Options: nsf, dod, nasa

# Model selection
export AI_MODEL=claude-sonnet-4-5  # or claude-opus-4

# Output directory
export OUTPUT_DIR=./custom_outputs
```

### Config.py Settings

```python
# Agency selection
Config.AGENCY = 'nsf'

# Cost targets
Config.TARGET_COST_MIN = 2.0
Config.TARGET_COST_MAX = 5.0

# Quality checking
Config.AUTO_TRIM_SECTIONS = True
Config.RUN_QUALITY_CHECKS = True
Config.SAVE_QUALITY_REPORT = True

# Workflow
Config.DEFAULT_ITERATIONS = 1  # Critique-refine cycles
```

## Examples

### Generate NSF Proposal

```bash
export GRANT_AGENCY=nsf
python main.py
```

Output:
- Deep_Space_Dynamics_NSF_SBIR_Phase1_TIMESTAMP.docx
- Deep_Space_Dynamics_NSF_Quality_Report_TIMESTAMP.md

### Generate DoD Proposal

```bash
export GRANT_AGENCY=dod
python main.py
```

Output:
- Deep_Space_Dynamics_DOD_SBIR_Phase1_TIMESTAMP.docx
- Deep_Space_Dynamics_DOD_Quality_Report_TIMESTAMP.md

### Generate NASA Proposal

```bash
export GRANT_AGENCY=nasa
python main.py
```

Output:
- Deep_Space_Dynamics_NASA_SBIR_Phase1_TIMESTAMP.docx
- Deep_Space_Dynamics_NASA_Quality_Report_TIMESTAMP.md

## Future Enhancements

Planned additions:
- Phase II templates for all agencies
- STTR (Small Business Technology Transfer) support
- Additional DoD branches (Navy, Army, etc.)
- State-level SBIR programs
- International grant programs
- Custom agency template builder UI
