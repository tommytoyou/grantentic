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
    SECRET_KEY = os.environ.get('SECRET_KEY', 'grantentic-secret-key-change-in-production')

    # ============================================================================
    # STRIPE PAYMENT CONFIGURATION
    # ============================================================================
    # Stripe API keys (set via environment variables in production)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')

    # Stripe Price IDs (create these in Stripe Dashboard)
    # One-time purchase: $800 for SBIR Phase I pre-application + full application
    STRIPE_PRICE_ONE_TIME = os.environ.get('STRIPE_PRICE_ONE_TIME', '')

    # Monthly subscription tiers (define pricing later)
    STRIPE_PRICE_MONTHLY_BASIC = os.environ.get('STRIPE_PRICE_MONTHLY_BASIC', '')
    STRIPE_PRICE_MONTHLY_PRO = os.environ.get('STRIPE_PRICE_MONTHLY_PRO', '')
    STRIPE_PRICE_MONTHLY_ENTERPRISE = os.environ.get('STRIPE_PRICE_MONTHLY_ENTERPRISE', '')

    # Payment tiers configuration
    PAYMENT_TIERS = {
        'one_time': {
            'name': 'SBIR Phase I Package',
            'description': 'Pre-application + Full Application',
            'price': 800,
            'price_id_env': 'STRIPE_PRICE_ONE_TIME',
            'type': 'one_time',
            'features': [
                'Complete SBIR Phase I pre-application',
                'Full SBIR Phase I proposal',
                'All supported agencies (NSF, DoD, NASA)',
                'Unlimited revisions for 30 days',
                'Quality assessment reports',
                'Word document export'
            ]
        },
        'monthly_basic': {
            'name': 'Basic',
            'description': 'Monthly Subscription',
            'price': 0,  # Define later
            'price_id_env': 'STRIPE_PRICE_MONTHLY_BASIC',
            'type': 'subscription',
            'features': ['TBD']
        },
        'monthly_pro': {
            'name': 'Pro',
            'description': 'Monthly Subscription',
            'price': 0,  # Define later
            'price_id_env': 'STRIPE_PRICE_MONTHLY_PRO',
            'type': 'subscription',
            'features': ['TBD']
        },
        'monthly_enterprise': {
            'name': 'Enterprise',
            'description': 'Monthly Subscription',
            'price': 0,  # Define later
            'price_id_env': 'STRIPE_PRICE_MONTHLY_ENTERPRISE',
            'type': 'subscription',
            'features': ['TBD']
        }
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
    # Number of critique-refine iterations per section
    # Higher values improve quality but increase cost
    DEFAULT_ITERATIONS = 1

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
