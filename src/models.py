from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class GrantSection(BaseModel):
    """Individual section of the grant proposal"""
    name: str
    content: str
    word_count: int
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
    
    total_word_count: int = 0
    total_cost: float = 0.0
    generation_time_seconds: float = 0.0
    
    def calculate_totals(self):
        """Calculate total word count across all sections"""
        self.total_word_count = (
            self.project_pitch.word_count +
            self.technical_objectives.word_count +
            self.broader_impacts.word_count +
            self.commercialization_plan.word_count
        )


class CostMetrics(BaseModel):
    """Track API usage costs"""
    section_name: str
    operation: str  # 'generate', 'critique', 'refine'
    input_tokens: int
    output_tokens: int
    cost_usd: float
    model: str = "claude-sonnet-4"
    timestamp: datetime = Field(default_factory=datetime.now)


class CompanyContext(BaseModel):
    """Company information for grant writing"""
    company_name: str
    founded: str
    location: str
    industry: str
    focus_area: str
    mission: str
    technology: Dict[str, Any]
    problem_statement: str
    solution: str
    team: List[Dict[str, str]]
    market_opportunity: Dict[str, Any]
    current_progress: Dict[str, Any]
    funding_needs: Dict[str, Any]
    intellectual_property: Dict[str, str]
    social_impact: str
