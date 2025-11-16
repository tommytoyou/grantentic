# 🚀 Grantentic - AI-Powered Grant Writing System

An advanced AI-powered system for generating professional SBIR Phase I grant proposals for NSF, DoD, and NASA. Features both a modern web interface and a powerful command-line tool.

## ✨ Key Features

### Multi-Agency Support
- **NSF** SBIR Phase I ($275K, 6 months) - Scientific innovation & broader impacts
- **DoD** SBIR Phase I ($200K, 6 months) - Military applications & dual-use technology
- **NASA** SBIR Phase I ($150K, 6 months) - Space applications & technology advancement

### Dual Interface
- **🌐 Web App (Streamlit):** Modern, user-friendly interface with real-time progress
- **💻 CLI:** Powerful command-line tool for automation and scripting

### AI-Powered Generation
- **Agentic Workflow:** Generate → Critique → Refine for high-quality output
- **Agency-Specific:** Automatically adapts tone, keywords, and structure per agency
- **Quality Checking:** 7 comprehensive validation checks with auto-trimming
- **Cost Efficient:** Typically $2-5 per complete proposal

## 🚀 Quick Start

### Web Application (Recommended)

**On Replit:**
1. Click the "Run" button
2. The web interface will launch automatically
3. Access via the webview panel

**Locally:**
```bash
streamlit run app.py
```

Then:
1. Edit company information in the "Company Info" tab
2. Select funding agency (NSF/DoD/NASA) in sidebar
3. Click "Generate Grant Proposal" in the "Generate Proposal" tab
4. Download results from the "Results" tab

### Command Line Interface

```bash
# Set agency
export GRANT_AGENCY=nsf  # Options: nsf, dod, nasa

# Generate proposal
python main.py

# Find outputs in outputs/ directory
ls outputs/
```

## 🌐 Web Interface Features

### Company Information Editor
- ✅ Form-based editing for all company fields
- ✅ JSON editor for team members
- ✅ Automatic validation and saving
- ✅ Persistent storage

### Real-Time Generation
- ✅ Live progress tracking by section
- ✅ Progressive cost updates
- ✅ Expandable status panels
- ✅ Progress bars

### Results Dashboard
- ✅ All sections in expandable tabs
- ✅ Quality report with improvement suggestions
- ✅ One-click Word document download
- ✅ Metrics: word count, cost, generation time

### Settings & Configuration
- ✅ Agency selector with funding details
- ✅ Critique-refine iteration control (0-3)
- ✅ Auto-trim toggle
- ✅ Real-time agency info display

## 💻 CLI Features

- ✅ Batch processing via scripts
- ✅ CI/CD integration
- ✅ Detailed console logging with Rich
- ✅ Automatic file output
- ✅ Environment variable configuration

## 📁 Project Structure

```
grantentic/
├── app.py                      # 🌐 Streamlit web application
├── main.py                     # 💻 CLI application
├── config.py                   # ⚙️ Configuration settings
├── requirements.txt            # 📦 Dependencies
│
├── agency_templates/           # 🏛️ Agency requirements
│   ├── nsf/requirements.json
│   ├── dod/requirements.json
│   └── nasa/requirements.json
│
├── data/                       # 📊 Company and agency data
│   ├── company_context.json
│   └── nsf_sbir_requirements.txt
│
├── src/                        # 🔧 Core modules
│   ├── agency_loader.py
│   ├── grant_agent.py
│   ├── agentic_workflow.py
│   ├── quality_checker.py
│   ├── docx_exporter.py
│   ├── cost_tracker.py
│   └── models.py
│
├── outputs/                    # 📄 Generated proposals
│   ├── *.docx
│   └── *_Quality_Report_*.md
│
└── docs/                       # 📚 Documentation
    ├── QUALITY_CHECKER.md
    └── MULTI_AGENCY_SUPPORT.md
```

## 🎯 Supported Agencies

### NSF (National Science Foundation)
- **Funding:** $275,000
- **Duration:** 6 months
- **Sections:** 8 required sections
- **Focus:** Scientific innovation, broader impacts, intellectual merit
- **Evaluation:** 50% Intellectual Merit, 25% Broader Impacts, 25% Commercialization

### DoD (Department of Defense)
- **Funding:** $200,000
- **Duration:** 6 months
- **Sections:** 9 required sections
- **Focus:** Military applications, dual-use technology, Phase III transition
- **Evaluation:** 40% Technical Merit, 30% DoD Relevance, 20% Commercialization, 10% Team

### NASA
- **Funding:** $150,000
- **Duration:** 6 months
- **Sections:** 9 required sections
- **Focus:** Space applications, technology advancement, mission alignment
- **Evaluation:** 35% Technical Merit, 35% NASA Relevance, 20% Commercialization, 10% Experience

## 🔧 Configuration

### Agency Selection

**Web App:** Use dropdown in sidebar

**CLI:** Set environment variable
```bash
export GRANT_AGENCY=nsf  # or dod, nasa
```

Or edit `config.py`:
```python
Config.AGENCY = 'nsf'
```

### Company Information

**Web App:** Use the visual editor in "Company Info" tab

**CLI:** Edit `data/company_context.json`:
```json
{
  "company_name": "Your Company",
  "focus_area": "Your technology focus",
  "mission": "Your mission",
  "problem_statement": "Problem you're solving",
  "solution": "Your solution",
  "team": [...]
}
```

### Advanced Settings

**Critique-Refine Iterations:**
- Web: Slider in sidebar (0-3)
- CLI: `Config.DEFAULT_ITERATIONS` in config.py

**Auto-Trim:**
- Web: Checkbox in sidebar
- CLI: `Config.AUTO_TRIM_SECTIONS` in config.py

## 📊 Quality Checks

7 comprehensive validation checks:

1. ✂️ **Page Limits** - Auto-trims sections exceeding limits
2. 🔑 **Required Keywords** - Validates agency-specific terminology
3. 💰 **Budget Validation** - Ensures correct funding amount
4. 📅 **Timeline Coverage** - Checks all months covered
5. 👥 **Team Bio Completeness** - Validates all team members
6. 📚 **Citation Detection** - Flags unsupported claims
7. 📖 **Readability Analysis** - Checks sentence complexity

## 📈 Cost Tracking

Both interfaces provide real-time cost tracking:

**Typical Costs:**
- NSF proposal: $2.50 - $4.00
- DoD proposal: $2.00 - $3.50
- NASA proposal: $2.00 - $3.50

**What's Included:**
- All section generation
- Critique and refinement
- Quality validation
- Document export

## 📄 Output Files

Generated files in `outputs/` directory:

```
outputs/
├── Company_Name_NSF_SBIR_Phase1_TIMESTAMP.docx
├── Company_Name_NSF_Quality_Report_TIMESTAMP.md
├── Company_Name_DOD_SBIR_Phase1_TIMESTAMP.docx
└── Company_Name_NASA_SBIR_Phase1_TIMESTAMP.docx
```

**Word Document contains:**
- Title page
- Table of contents
- All proposal sections
- Professional formatting
- Metadata footer

**Quality Report contains:**
- Executive summary with quality score
- Detailed validation results
- Improvement recommendations
- Next steps guidance

## 🚀 Deployment

### Replit (Automatic)
1. Fork/import this Repl
2. Click "Run"
3. Web app launches automatically

### Local Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Set up API keys (if not using Replit)
export AI_INTEGRATIONS_ANTHROPIC_API_KEY=your_key
export AI_INTEGRATIONS_ANTHROPIC_BASE_URL=your_url

# Run web app
streamlit run app.py

# Or run CLI
python main.py
```

## 🎓 Best Practices

### For NSF Proposals
- ✅ Emphasize broader societal impacts
- ✅ Use accessible language for non-specialists
- ✅ Highlight diversity and inclusion efforts
- ✅ Show clear scientific advancement

### For DoD Proposals
- ✅ Identify specific military capability gaps
- ✅ Emphasize dual-use applications
- ✅ Show path to Phase III (DoD sales)
- ✅ Reference specific DoD requirements

### For NASA Proposals
- ✅ Align with specific NASA missions
- ✅ Reference NASA Technology Taxonomy
- ✅ Show TRL advancement plan (typically 2→4)
- ✅ Identify NASA center partnerships

## 🐛 Troubleshooting

### Web App Issues

**Generation hangs:**
- Check API keys are configured
- Verify internet connection
- Check browser console for errors

**Download not working:**
- Ensure generation completed successfully
- Check `outputs/` directory exists
- Try refreshing the page

### CLI Issues

**Module not found:**
```bash
pip install -r requirements.txt
```

**API key errors:**
```bash
export AI_INTEGRATIONS_ANTHROPIC_API_KEY=your_key
export AI_INTEGRATIONS_ANTHROPIC_BASE_URL=your_url
```

## 📚 Documentation

Comprehensive docs in `docs/`:

- **QUALITY_CHECKER.md** - Quality validation system details
- **MULTI_AGENCY_SUPPORT.md** - Agency-specific guidelines

## 🏢 First Customer

**Deep Space Dynamics** - Boulder-based aerospace startup developing CubeSat constellations for asteroid detection and planetary defense.

## 💡 Technology Stack

- **Python 3.11**
- **Anthropic Claude API** (Sonnet 4.5)
- **Streamlit** - Web interface
- **python-docx** - Document generation
- **Pydantic** - Data validation
- **Rich** - CLI output

## 📞 Support

1. Check this README
2. Review `docs/` directory
3. Check troubleshooting section
4. Submit issue on GitHub

---

**Built with ❤️ for innovators advancing humanity's future**

Generate professional grant proposals in minutes, not weeks!
