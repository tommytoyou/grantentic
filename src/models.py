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
    """Complete grant proposal"""
    company_name: str
    grant_type: str = "NSF SBIR Phase I"
    created_at: datetime = Field(default_factory=datetime.now)

    project_pitch: GrantSection
    technical_objectives: GrantSection
    broader_impacts: GrantSection
    commercialization_plan: GrantSection
    budget_justification: GrantSection
    work_plan: GrantSection
    biographical_sketches: GrantSection
    facilities_equipment: GrantSection

    total_word_count: int = 0
    total_cost: float = 0.0
    generation_time_seconds: float = 0.0

    def calculate_totals(self):
        """Calculate total word count across all sections"""
        self.total_word_count = (
            self.project_pitch.word_count +
            self.technical_objectives.word_count +
            self.broader_impacts.word_count +
            self.commercialization_plan.word_count +
            self.budget_justification.word_count +
            self.work_plan.word_count +
            self.biographical_sketches.word_count +
            self.facilities_equipment.word_count
        )


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
    tier: str  # 'one_time', 'monthly_basic', 'monthly_pro', 'monthly_enterprise'
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None


class SubscriptionRecord(BaseModel):
    """Record of a subscription"""
    subscription_id: str
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    tier: str  # 'monthly_basic', 'monthly_pro', 'monthly_enterprise'
    status: str  # 'active', 'canceled', 'past_due', 'unpaid'
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    canceled_at: Optional[datetime] = None


class UserPaymentStatus(BaseModel):
    """User's payment and subscription status"""
    has_paid: bool = False
    payment_type: Optional[str] = None  # 'one_time' or 'subscription'
    one_time_purchase: Optional[PaymentRecord] = None
    subscription: Optional[SubscriptionRecord] = None
    stripe_customer_id: Optional[str] = None
    # For one-time purchases: expiration for revision access
    one_time_expires_at: Optional[datetime] = None
    # Usage tracking
    proposals_generated: int = 0
