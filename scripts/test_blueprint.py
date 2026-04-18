"""
One-off smoke test for the SBIR Blueprint pipeline.

Exercises src.blueprint end-to-end using realistic fake intake data:
    1. generate_blueprint_content  -> Claude API call
    2. create_blueprint_pdf        -> ReportLab PDF build
    3. create_prompt_pack_pdf      -> ReportLab PDF build
    4. send_blueprint_email        -> Resend (only if RESEND_API_KEY + TEST_EMAIL set)

Designed to be run as a Render one-off job so the Anthropic key that is
already configured on the service is used. The script reads every secret
from environment variables — nothing is hardcoded.

Required env:
    AI_INTEGRATIONS_ANTHROPIC_API_KEY   (or ANTHROPIC_API_KEY)

Optional env:
    AI_INTEGRATIONS_ANTHROPIC_BASE_URL  custom base URL
    AI_MODEL                            override Config.MODEL
    GRANT_AGENCY                        defaults to "nsf"; also accepts "dod", "nasa"
    RESEND_API_KEY + TEST_EMAIL         if both set, an email with the PDFs is sent
    BLUEPRINT_TEST_OUT_DIR              where to write the PDFs (default: /tmp)

Usage:
    python scripts/test_blueprint.py
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    api_key = (
        os.environ.get("AI_INTEGRATIONS_ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
    )
    if not api_key:
        print(
            "ERROR: no Anthropic API key found. Set "
            "AI_INTEGRATIONS_ANTHROPIC_API_KEY or ANTHROPIC_API_KEY.",
            file=sys.stderr,
        )
        return 1

    agency = os.environ.get("GRANT_AGENCY", "nsf").lower()
    if agency not in {"nsf", "dod", "nasa"}:
        print(f"ERROR: unsupported agency {agency!r}. Use nsf, dod, or nasa.", file=sys.stderr)
        return 1

    out_dir = Path(os.environ.get("BLUEPRINT_TEST_OUT_DIR", "/tmp"))
    out_dir.mkdir(parents=True, exist_ok=True)

    # Import after sys.path setup so local modules resolve.
    from src.blueprint import (
        create_blueprint_pdf,
        create_prompt_pack_pdf,
        generate_blueprint_content,
        send_blueprint_email,
    )

    intake = {
        "company_name": "Acme Photonics",
        "problem": (
            "Semiconductor fabs lose an estimated $2B per year to undetected "
            "sub-wavelength defects on advanced EUV masks. Existing inspection "
            "tools miss ~15% of critical defects at the 3nm node."
        ),
        "who_suffers": (
            "Top-5 logic foundries (TSMC, Samsung, Intel) and their customers; "
            "yield losses compound into a 3-6 week delay per affected tapeout, "
            "costing roughly $8-12M per incident."
        ),
        "why_current_fail": (
            "Current actinic inspection tools cost >$150M and still rely on "
            "deterministic image-diff algorithms that cannot separate true "
            "defects from stochastic EUV shot noise below 8nm critical dimension."
        ),
        "technology": (
            "A physics-informed diffusion model that learns the forward EUV "
            "imaging operator from paired aerial-image / wafer-CD data, then "
            "runs Bayesian posterior inference to assign a calibrated defect "
            "probability to every suspect pixel. The novel contribution is the "
            "integration of a differentiable Abbe imaging kernel as the score "
            "network's physics prior."
        ),
        "dev_stage": "proof_of_concept",
        "phase1_output": (
            "A validated Bayesian defect-probability model demonstrated on a "
            "labeled dataset of 5,000 real EUV mask defects, with a target "
            "false-negative rate below 2% at a fixed 5% false-positive budget."
        ),
        "competitors": (
            "KLA-Tencor (Teron 650e) — high capex, poor stochastic-noise handling. "
            "Applied Materials (Aera5) — strong hardware but closed-model software. "
            "Lasertec (ACTIS A300) — actinic leader, lacks ML-based classification."
        ),
        "differentiator": (
            "Only approach that combines a learned score network with a "
            "differentiable physics kernel, producing calibrated per-pixel "
            "uncertainty instead of a binary pass/fail decision."
        ),
        "market_size": (
            "EUV mask inspection tools: $4.2B TAM in 2026, growing to $7.8B by "
            "2030 (SEMI data). Software-only subsegment (our initial wedge): "
            "~$600M SAM."
        ),
        "pi_background": (
            "Dr. Jane Rivera — PhD Applied Physics (Stanford, 2018); 6 years at "
            "ASML as senior computational lithography engineer; 14 peer-reviewed "
            "publications on EUV imaging models; co-inventor on 3 granted U.S. "
            "patents."
        ),
        "team_members": (
            "Dr. Marcus Chen, CTO — 10 years ML research at NVIDIA, specialized "
            "in diffusion models. Dr. Priya Natarajan, Senior Scientist — former "
            "KLA principal engineer, defect-detection domain expert."
        ),
        "prior_work": (
            "NSF Phase I award #2134567 (2023, Rivera PI) on adjacent "
            "computational-lithography project. 2 journal publications in Optics "
            "Express (2024, 2025). Provisional patent filed Nov 2025 on the "
            "physics-informed score network."
        ),
        "solicitation": "NSF SBIR Phase I Topic AM (Advanced Manufacturing)",
    }

    company_name = intake["company_name"]

    print(f"[1/3] calling Claude to generate Blueprint content (agency={agency})...")
    content = generate_blueprint_content(intake, agency)
    print(f"      -> {len(content):,} chars returned")
    preview = content[:400].replace("\n", " ")
    print(f"      preview: {preview}...")

    print("[2/3] rendering Blueprint PDF...")
    blueprint_pdf = create_blueprint_pdf(company_name, agency, content)
    bp_path = out_dir / f"test_blueprint_{agency}.pdf"
    bp_path.write_bytes(blueprint_pdf)
    print(f"      -> wrote {bp_path} ({len(blueprint_pdf):,} bytes)")

    print("[3/3] rendering Prompt Pack PDF...")
    prompt_pack_pdf = create_prompt_pack_pdf(agency)
    pp_path = out_dir / f"test_prompt_pack_{agency}.pdf"
    pp_path.write_bytes(prompt_pack_pdf)
    print(f"      -> wrote {pp_path} ({len(prompt_pack_pdf):,} bytes)")

    test_email = os.environ.get("TEST_EMAIL")
    resend_key = os.environ.get("RESEND_API_KEY")
    if test_email and resend_key:
        print(f"[bonus] sending test email to {test_email}...")
        ok = send_blueprint_email(
            test_email, company_name, agency, blueprint_pdf, prompt_pack_pdf
        )
        print(f"      -> send_blueprint_email returned {ok}")
    else:
        print("[bonus] skipping email send (set TEST_EMAIL and RESEND_API_KEY to enable)")

    print("\nDONE: Blueprint pipeline smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
