from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class GrantSection(BaseModel):
    """Individual section of the grant proposal"""
    name: str
    content: str
    word_count: int
    char_count: int = 0
    iteration: int = 0
    critique: Optional[str] = None
    refinement_notes: Optional[str] = None


class GrantProposal(BaseModel):
    """Complete grant proposal — an ordered list of sections whose names
    are defined by the active agency's requirements.json (source of truth)."""
    company_name: str
    grant_type: str = "NSF SBIR Phase I"
    created_at: datetime = Field(default_factory=datetime.now)

    sections: List[GrantSection] = Field(default_factory=list)

    total_word_count: int = 0
    total_cost: float = 0.0
    generation_time_seconds: float = 0.0

    def calculate_totals(self):
        """Sum word counts across every section in the proposal."""
        self.total_word_count = sum(s.word_count for s in self.sections)

    def get_section(self, name: str) -> Optional[GrantSection]:
        """Look up a section by its agency-defined name (case-insensitive)."""
        target = name.lower().strip()
        for s in self.sections:
            if s.name.lower().strip() == target:
                return s
        return None


class CostMetrics(BaseModel):
    """Track API usage costs"""
    section_name: str
    operation: str  # 'generate', 'critique', 'refine'
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str = "claude-sonnet-4-5"
    timestamp: datetime = Field(default_factory=datetime.now)


class CompanyContext(BaseModel):
    """Company information for grant writing"""

    model_config = {"extra": "ignore"}

    company_name: str = ""
    founded: str = ""
    location: str = ""
    industry: str = ""
    focus_area: str = ""

    # Core Innovation (replaces the old free-text "mission")
    primary_innovation: str = ""
    development_stage: str = ""
    phase1_proof: str = ""

    # Technical Problem (replaces free-text "problem_statement")
    who_suffers: str = ""
    existing_solutions_fail: str = ""
    core_technical_unknown: str = ""

    # Technical Approach (replaces free-text "solution")
    technical_approach: str = ""
    technical_novelty: str = ""
    technical_risks: str = ""

    # Market and Customers
    primary_customers: str = ""
    market_size: str = ""
    why_now: str = ""

    # Team
    team: List[Dict[str, str]] = Field(default_factory=list)
    advisory_board: List[Dict[str, str]] = Field(default_factory=list)
    key_partnerships: str = ""

    # Legacy fields kept so older saved contexts still validate.
    mission: str = ""
    technology: Dict[str, Any] = Field(default_factory=dict)
    problem_statement: str = ""
    solution: str = ""
    market_opportunity: Dict[str, Any] = Field(default_factory=dict)
    current_progress: Dict[str, Any] = Field(default_factory=dict)
    funding_needs: Dict[str, Any] = Field(default_factory=dict)
    intellectual_property: Dict[str, Any] = Field(default_factory=dict)
    social_impact: str = ""


class PaymentRecord(BaseModel):
    """Record of a payment transaction"""
    payment_id: str
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    amount_cents: int
    currency: str = "usd"
    status: str  # 'pending', 'completed', 'failed', 'refunded'
    tier: str  # 'nsf_pitch', 'nsf_full', 'nsf_bundle', 'blueprint'
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class UserPaymentStatus(BaseModel):
    """User's payment status"""
    has_paid: bool = False
    last_purchase: Optional[PaymentRecord] = None
    stripe_customer_id: Optional[str] = None
    proposals_generated: int = 0
