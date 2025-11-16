# Enhanced Quality Checking System

The Grantentic quality checking system provides comprehensive validation and automated improvements for NSF SBIR Phase I grant proposals.

## Features

### 1. Auto-Trim Sections Exceeding Page Limits ✂️

**What it does:**
- Automatically trims sections that exceed NSF page limits
- Intelligently finds sentence boundaries to preserve meaning
- Adds a notice indicating content was trimmed
- Updates word count and tracking information

**Page Limits:**
| Section | Min Pages | Max Pages | Min Words | Max Words |
|---------|-----------|-----------|-----------|-----------|
| Project Pitch | 1 | 2 | 400 | 800 |
| Technical Objectives | 5 | 6 | 2,000 | 2,400 |
| Broader Impacts | 1 | 2 | 400 | 800 |
| Commercialization Plan | 2 | 3 | 800 | 1,200 |
| Budget & Justification | 2 | 3 | 800 | 1,200 |
| Work Plan & Timeline | 2 | 3 | 800 | 1,200 |
| Biographical Sketches | 2 | 8 | 800 | 3,200 |
| Facilities & Equipment | 1 | 2 | 400 | 800 |

**Example:**
```
Section: Technical Objectives
Original: 2,800 words
Auto-trimmed to: 2,400 words
Status: ✂️ Auto-trimmed (2,800 → 2,400 words)
```

### 2. Required Keywords Validation 🔑

**What it does:**
- Checks each section for NSF-required keywords
- Identifies missing critical terms
- Provides specific recommendations for missing keywords

**Required Keywords by Section:**

- **Project Pitch:** innovation, problem, solution, market, Phase I
- **Technical Objectives:** methodology, risk, milestone, feasibility, TRL
- **Broader Impacts:** societal, impact, benefit, broader
- **Commercialization Plan:** market, customer, revenue, competitive, commercialization
- **Budget & Justification:** personnel, equipment, overhead, justification
- **Work Plan & Timeline:** month, milestone, timeline, deliverable
- **Biographical Sketches:** education, experience, PhD, publications
- **Facilities & Equipment:** facilities, equipment, resources

### 3. Budget Total Validation 💰

**What it does:**
- Parses budget section for dollar amounts
- Identifies the total budget amount
- Validates it equals exactly $275,000
- Calculates difference if not exact

**Example Output:**
```
✓ Budget totals exactly $275,000.00
Target: $275,000.00
Actual: $275,000.00
```

**If budget is incorrect:**
```
⚠️ Budget is $280,000.00 (+$5,000.00 from target)
Suggestion: Adjust line items by $5,000.00 to match NSF SBIR Phase I funding limit.
```

### 4. Timeline Coverage Check 📅

**What it does:**
- Scans work plan for month references (Month 1, Month 2, etc.)
- Validates all 6 months of Phase I are covered
- Identifies missing months

**Validation:**
- Looks for patterns: "Month 1", "M1", "1 month", etc.
- Checks months 1-6 are all mentioned
- Provides specific recommendations for missing months

**Example Output:**
```
✓ Timeline covers 6-month Phase I period
Months mentioned: 1, 2, 3, 4, 5, 6
Coverage: 6/6 months
```

### 5. Team Member Bio Completeness ✅

**What it does:**
- Extracts team members from company context
- Checks if each member has a biographical sketch
- Validates bios contain education and experience info
- Identifies missing team member bios

**Validation Criteria:**
- Name appears in biographical sketches section
- Contains education keywords (PhD, Master, Bachelor, degree, university)
- Contains background/experience information

**Example Output:**
```
✓ All team members have bios
  ✓ Dr. Sarah Chen (CEO & Co-founder)
  ✓ Dr. Marcus Rodriguez (CTO & Co-founder)
  ✓ Dr. Emily Wang (Chief Data Scientist)
  ✓ James Mitchell (VP of Engineering)
```

**If incomplete:**
```
⚠️ 1 team member(s) missing bios
  ✓ Dr. Sarah Chen (CEO & Co-founder)
  ❌ Dr. Marcus Rodriguez (CTO & Co-founder)

Suggestion: Missing bio for Dr. Marcus Rodriguez (CTO & Co-founder).
Add a comprehensive 2-page biographical sketch including education,
experience, and relevant publications.
```

### 6. Citation and Claims Detection 📚

**What it does:**
- Identifies statements that should have citations
- Detects market size claims, statistics, research references
- Checks for citation presence
- Flags unsupported claims

**Claim Patterns Detected:**
- "studies show", "research indicates"
- Percentages (e.g., "94%")
- Market sizes (e.g., "$2.8B market")
- Agency references (NASA, DOD, NSF, etc.)

**Citation Patterns Recognized:**
- Academic: (Author et al., 2023)
- Numbered: [1], [2,3]
- URLs: http://, https://

**Example Output:**
```
✓ Technical Objectives: 5 claim(s), 3 citation(s)
⚠️ Commercialization Plan: 8 claim(s) found, no citations

Suggestion: Found 8 claim(s) without citations. Add references to
support statements about market size, research findings, and technical claims.
```

### 7. Comprehensive Quality Report 📋

**What it generates:**
- Executive summary with overall quality score
- Detailed results for all 7 validation checks
- Specific improvement suggestions
- Next steps recommendations
- Saved as Markdown file in `outputs/` directory

**Quality Score Ratings:**
- 90-100%: EXCELLENT ✅
- 75-89%: GOOD ⚠️ (minor improvements)
- 60-74%: FAIR ⚠️ (several areas need attention)
- <60%: NEEDS WORK ❌ (significant revisions required)

**Report Structure:**
```markdown
# NSF SBIR Phase I Proposal - Quality Report

**Overall Quality Score:** 85.5% (47/55 checks passed)
⚠️ **Status:** GOOD - Minor improvements recommended

## Detailed Quality Checks

### 1. Page Limits and Word Counts
- ✓ Project Pitch: 650 words (target: 400-800 words)
- ✂️ Technical Objectives: Auto-trimmed (2,800 → 2,400 words)
...

### 2. Required Keywords
- ✓ Project Pitch: 5/5 keywords found
- ⚠️ Technical Objectives: 4/5 keywords found
  - Missing: TRL
...

## 🎯 Recommended Improvements

1. **Technical Objectives**: Missing required keywords: TRL.
   These are important for NSF reviewers.

2. **Commercialization Plan**: Found 8 claim(s) without citations.
   Add references for market size claims.

...

## Next Steps

1. Address all items in 'Recommended Improvements' section
2. Re-run quality checker after revisions
3. Have proposal reviewed by domain expert
4. Revise and resubmit for quality check
```

## Readability Analysis 📖

**What it checks:**
- Average sentence length (warns if >30 words)
- Passive voice indicators
- Overall clarity and accessibility

**Example:**
```
✓ Project Pitch: Good readability (avg 22.3 words/sentence)
⚠️ Technical Objectives: Avg sentence length 32.5 words (>30)

Suggestion: Consider breaking up complex sentences for better readability.
```

## Usage

The quality checker runs automatically at the end of proposal generation:

```python
# In main.py
validation_results = quality_checker.validate_proposal(proposal, company_context)
```

**Output Files:**
1. **Word Document:** Full proposal with auto-trimmed sections
2. **Quality Report (Markdown):** `outputs/Company_Quality_Report_TIMESTAMP.md`

**Console Output:**
```
✅ Grant Generation Complete!

📄 Proposal: outputs/Deep_Space_Dynamics_NSF_SBIR_Phase1_20250116_143022.docx
📋 Quality Report: outputs/Deep_Space_Dynamics_Quality_Report_20250116_143022.md
📊 Total Words: 8,245
💰 Total Cost: $4.23
⏱️  Generation Time: 127.3s
✂️  Auto-trimmed: 2 section(s)
💡 Suggestions: 5 improvement(s) recommended
```

## Benefits

1. **Time Savings:** Automatic trimming eliminates manual editing
2. **Compliance:** Ensures all NSF requirements are met
3. **Quality:** Identifies weaknesses before submission
4. **Traceability:** Comprehensive report documents all issues
5. **Confidence:** Clear next steps for improvements

## Advanced Features

### Auto-Apply Trimmed Sections

Trimmed sections are automatically applied to the proposal object:

```python
# Sections are modified in-place
for section_key, trimmed_section in trimmed_sections.items():
    setattr(proposal, section_key, trimmed_section)
```

### Backward Compatibility

The quality checker works with or without company context:

```python
# Enhanced mode (recommended)
quality_checker.validate_proposal(proposal, company_context)

# Legacy mode (limited checks)
quality_checker.validate_proposal(proposal)
```

## Customization

You can customize validation thresholds in `src/quality_checker.py`:

```python
# Adjust page limits
self.page_limits = {
    "project_pitch": (1, 2, 400, 800),  # (min_pages, max_pages, min_words, max_words)
    ...
}

# Adjust required keywords
self.required_keywords = {
    "Project Pitch": ["innovation", "problem", ...],
    ...
}
```

## Troubleshooting

**Issue:** Budget total not detected
- **Solution:** Ensure budget clearly states "Total: $275,000" with dollar sign

**Issue:** Timeline months not detected
- **Solution:** Use explicit format: "Month 1", "Month 2", etc.

**Issue:** Team bios not recognized
- **Solution:** Ensure exact name matches from company_context.json

**Issue:** Too many false positive claims
- **Solution:** Add citations in standard format: [1] or (Author, 2023)

## Future Enhancements

Planned features:
- Grammar and spell checking
- Jargon detection
- Reference list validation
- Compliance with specific NSF solicitations
- AI-powered suggestion implementation
