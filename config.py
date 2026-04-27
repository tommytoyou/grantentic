"""
Configuration file for Grantentic Grant Writing System
"""
import os
from typing import Optional

class Config:
    """Application configuration"""

    # ============================================================================
    # WEB APPLICATION
    # ============================================================================
    SECRET_KEY = os.environ.get('SECRET_KEY', '')

    # ============================================================================
    # SUPABASE DATABASE
    # ============================================================================
    # The app authenticates users itself (SHA-256 + salt in src/auth.py) and
    # makes every database call from the server, so we use the service_role key
    # for all queries. service_role bypasses RLS, which is correct here because
    # the app — not Supabase Auth — gates which rows each user can access.
    # The anon key is kept only for clients that might talk to Supabase directly
    # from the browser in the future.
    # ============================================================================
    # EMAIL (Resend)
    # ============================================================================
    RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    # ============================================================================
    # STRIPE PAYMENT CONFIGURATION
    # ============================================================================
    # Stripe API keys (set via environment variables in production)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Blueprint product
    STRIPE_PRICE_BLUEPRINT = os.environ.get('STRIPE_PRICE_BLUEPRINT', '')          # $49
    STRIPE_PRICE_BLUEPRINT_STUDENT = os.environ.get('STRIPE_PRICE_BLUEPRINT_STUDENT', '')  # $19
    BLUEPRINT_LAUNCH_DATE = os.environ.get('BLUEPRINT_LAUNCH_DATE', '2026-05-15T00:00:00Z')

    # NSF product Stripe price IDs (create in Stripe Dashboard)
    STRIPE_PRICE_NSF_PITCH = os.environ.get('STRIPE_PRICE_NSF_PITCH', '')   # $149
    STRIPE_PRICE_NSF_FULL = os.environ.get('STRIPE_PRICE_NSF_FULL', '')     # $449
    STRIPE_PRICE_NSF_BUNDLE = os.environ.get('STRIPE_PRICE_NSF_BUNDLE', '') # $549

    NSF_PRODUCTS = {
        'pitch': {
            'name': 'NSF Project Pitch Generator',
            'price_cents': 14900,
            'price_id_env': 'STRIPE_PRICE_NSF_PITCH',
            'requires_invitation': False,
            'expert_review': False,
        },
        'full': {
            'name': 'NSF Full Proposal Generator',
            'price_cents': 44900,
            'price_id_env': 'STRIPE_PRICE_NSF_FULL',
            'requires_invitation': True,
            'expert_review': True,
        },
        'bundle': {
            'name': 'NSF Complete Bundle',
            'price_cents': 54900,
            'price_id_env': 'STRIPE_PRICE_NSF_BUNDLE',
            'requires_invitation': True,
            'expert_review': True,
            'separately_cents': 59800,
            'savings_cents': 4900,
        },
    }

    # Base URL for Stripe redirects (set in production)
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:8000')

    # ============================================================================
    # AGENCY SELECTION
    # ============================================================================
    # Set your target funding agency here
    # Options: 'nsf', 'dod', 'nasa'
    AGENCY = os.environ.get('GRANT_AGENCY', 'nsf').lower()

    # ============================================================================
    # AGENCY-SPECIFIC SETTINGS
    # ============================================================================
    # These are automatically loaded based on AGENCY selection
    # Override here if needed for custom configurations

    AGENCY_TEMPLATES_DIR = 'agency_templates'

    # ============================================================================
    # AI MODEL CONFIGURATION
    # ============================================================================
    # Model to use for grant generation
    # Options: 'claude-sonnet-4-5', 'claude-opus-4'
    MODEL = os.environ.get('AI_MODEL', 'claude-sonnet-4-5')

    # Maximum tokens for generation (affects cost and output length)
    MAX_TOKENS_GENERATE = 6000
    MAX_TOKENS_CRITIQUE = 2000
    MAX_TOKENS_REFINE = 6000

    # ============================================================================
    # QUALITY CHECKING
    # ============================================================================
    # Enable automatic section trimming
    AUTO_TRIM_SECTIONS = True

    # Enable quality validation
    RUN_QUALITY_CHECKS = True

    # Save quality report
    SAVE_QUALITY_REPORT = True

    # ============================================================================
    # OUTPUT SETTINGS
    # ============================================================================
    OUTPUT_DIR = 'outputs'

    # Include metadata in document footer
    INCLUDE_METADATA = True

    # ============================================================================
    # COST TRACKING
    # ============================================================================
    # Target cost range for proposal generation (USD)
    TARGET_COST_MIN = 2.0
    TARGET_COST_MAX = 5.0

    # ============================================================================
    # WORKFLOW SETTINGS
    # ============================================================================
    # Number of critique-refine iterations per section.
    # Every NSF product runs full-quality generation at this level.
    DEFAULT_ITERATIONS = 2

    # Enable parallel section generation (not yet implemented)
    PARALLEL_GENERATION = False

    # ============================================================================
    # AGENCY PROFILES
    # ============================================================================
    AGENCY_PROFILES = {
        'nsf': {
            'name': 'National Science Foundation',
            'program': 'SBIR Phase I',
            'funding_amount': 275000,
            'duration_months': 6,
            'template_dir': 'nsf',
            'description': 'NSF SBIR Phase I - Focus on scientific innovation and broader impacts'
        },
        'dod': {
            'name': 'Department of Defense',
            'program': 'SBIR Phase I',
            'funding_amount': 200000,
            'duration_months': 6,
            'template_dir': 'dod',
            'description': 'DoD SBIR Phase I - Focus on military applications and dual-use technology'
        },
        'nasa': {
            'name': 'NASA',
            'program': 'SBIR Phase I',
            'funding_amount': 150000,
            'duration_months': 6,
            'template_dir': 'nasa',
            'description': 'NASA SBIR Phase I - Focus on space applications and technology advancement'
        }
    }

    @classmethod
    def get_agency_info(cls) -> dict:
        """Get information about the currently selected agency"""
        return cls.AGENCY_PROFILES.get(cls.AGENCY, cls.AGENCY_PROFILES['nsf'])

    @classmethod
    def get_agency_template_path(cls) -> str:
        """Get path to agency template directory"""
        agency_info = cls.get_agency_info()
        return os.path.join(cls.AGENCY_TEMPLATES_DIR, agency_info['template_dir'])

    @classmethod
    def get_requirements_file(cls) -> str:
        """Get path to agency requirements JSON file"""
        return os.path.join(cls.get_agency_template_path(), 'requirements.json')

    @classmethod
    def validate_agency(cls) -> bool:
        """Validate that selected agency is supported"""
        return cls.AGENCY in cls.AGENCY_PROFILES

    @classmethod
    def get_funding_amount(cls) -> int:
        """Get funding amount for selected agency"""
        return cls.get_agency_info()['funding_amount']

    @classmethod
    def get_duration_months(cls) -> int:
        """Get project duration for selected agency"""
        return cls.get_agency_info()['duration_months']

    @classmethod
    def list_available_agencies(cls) -> list:
        """List all available funding agencies"""
        return list(cls.AGENCY_PROFILES.keys())

    @classmethod
    def print_agency_info(cls):
        """Print information about current agency selection"""
        if not cls.validate_agency():
            print(f"⚠️  Warning: Unknown agency '{cls.AGENCY}'. Defaulting to NSF.")
            cls.AGENCY = 'nsf'

        info = cls.get_agency_info()
        print(f"\n{'='*70}")
        print(f"Selected Agency: {info['name']}")
        print(f"Program: {info['program']}")
        print(f"Funding Amount: ${info['funding_amount']:,}")
        print(f"Duration: {info['duration_months']} months")
        print(f"{'='*70}\n")


# ============================================================================
# ENVIRONMENT-SPECIFIC OVERRIDES
# ============================================================================
# These can be set via environment variables

# Override agency selection
# Example: export GRANT_AGENCY=dod
if 'GRANT_AGENCY' in os.environ:
    Config.AGENCY = os.environ['GRANT_AGENCY'].lower()

# Override model selection
# Example: export AI_MODEL=claude-opus-4
if 'AI_MODEL' in os.environ:
    Config.MODEL = os.environ['AI_MODEL']

# Override output directory
# Example: export OUTPUT_DIR=/path/to/outputs
if 'OUTPUT_DIR' in os.environ:
    Config.OUTPUT_DIR = os.environ['OUTPUT_DIR']
