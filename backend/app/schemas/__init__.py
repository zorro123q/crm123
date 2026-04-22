"""
Pydantic schemas.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.services.crm_rules_service import (
    DEFAULT_OPPORTUNITY_STAGE,
    LEAD_STATUSES,
    OPPORTUNITY_STATUSES,
    STAGE_ORDER,
    normalize_lead_status,
    normalize_opportunity_stage,
)
from app.services.scoring_service import SCORING_FIELD_KEYS, is_valid_option


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    is_admin: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class UserUpdateRequest(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=100)
    password: str | None = Field(None, min_length=1, max_length=255)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=1, max_length=255)
    confirm_password: str = Field(..., min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_passwords(self):
        if not self.current_password.strip():
            raise ValueError("Current password is required")
        if not self.new_password.strip():
            raise ValueError("New password is required")
        if not self.confirm_password.strip():
            raise ValueError("Please confirm the new password")
        if self.new_password != self.confirm_password:
            raise ValueError("The two new passwords do not match")
        return self


class MessageResponse(BaseModel):
    message: str


class ScoringDimensionsInput(BaseModel):
    industry: str | None = None
    industry_rank: str | None = None
    scene: str | None = None
    budget: str | None = None
    labor_cost: str | None = None
    daily_calls: str | None = None
    leader_owner: str | None = None
    lowest_price: str | None = None
    initiator_department: str | None = None
    competitor: str | None = None
    bidding_type: str | None = None
    has_ai_project: str | None = None
    customer_service_size: str | None = None
    region: str | None = None

    @model_validator(mode="after")
    def validate_scoring_dimensions(self):
        for field_name in SCORING_FIELD_KEYS:
            value = getattr(self, field_name)
            if not is_valid_option(field_name, value):
                raise ValueError(f"Invalid scoring option for {field_name}: {value}")
        return self


class OpportunityCreate(ScoringDimensionsInput):
    name: str = Field(..., min_length=1, max_length=500)
    account_id: UUID | None = None
    contact_id: UUID | None = None
    stage: str = DEFAULT_OPPORTUNITY_STAGE
    status: str | None = "new"
    amount: float | None = None
    probability: int | None = Field(None, ge=0, le=100)
    close_date: date | None = None
    source: str | None = None
    ai_confidence: float | None = Field(None, ge=0.0, le=1.0)
    ai_raw_text: str | None = None
    ai_extracted: dict[str, Any] | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value: str):
        return normalize_opportunity_stage(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None):
        normalized = str(value or "").strip().lower() or "new"
        if normalized not in OPPORTUNITY_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(OPPORTUNITY_STATUSES)}")
        return normalized


class OpportunityUpdate(ScoringDimensionsInput):
    name: str | None = None
    stage: str | None = None
    status: str | None = None
    amount: float | None = None
    probability: int | None = Field(None, ge=0, le=100)
    close_date: date | None = None
    source: str | None = None
    custom_fields: dict[str, Any] | None = None

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value: str | None):
        if value is None:
            return value
        return normalize_opportunity_stage(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None):
        if value is None:
            return value
        normalized = str(value).strip().lower()
        if normalized not in OPPORTUNITY_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(OPPORTUNITY_STATUSES)}")
        return normalized


class OpportunityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    stage: str
    status: str
    amount: float | None = None
    probability: int | None = None
    close_date: date | None = None
    source: str | None = None
    card_score: int = 0
    card_level: str = "E"
    industry: str | None = None
    industry_rank: str | None = None
    scene: str | None = None
    budget: str | None = None
    labor_cost: str | None = None
    daily_calls: str | None = None
    leader_owner: str | None = None
    lowest_price: str | None = None
    initiator_department: str | None = None
    competitor: str | None = None
    bidding_type: str | None = None
    has_ai_project: str | None = None
    customer_service_size: str | None = None
    region: str | None = None
    score_detail_json: dict[str, Any] = Field(default_factory=dict)
    ai_confidence: float | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    stage_history: list[dict[str, Any]] = Field(default_factory=list)
    owner_id: UUID | None = None
    owner_username: str | None = None
    owner: UserOut | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class StageMoveRequest(BaseModel):
    stage: str
    opp_id: UUID

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value: str):
        return normalize_opportunity_stage(value)


class LeadCreate(ScoringDimensionsInput):
    name: str = Field(..., min_length=1, max_length=255)
    company: str | None = Field(None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    source: str | None = Field(None, max_length=100)
    status: str = "new"
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str):
        return normalize_lead_status(value)


class LeadUpdate(ScoringDimensionsInput):
    name: str | None = None
    company: str | None = Field(None, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(None, max_length=50)
    source: str | None = Field(None, max_length=100)
    status: str | None = None
    custom_fields: dict[str, Any] | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None):
        if value is None:
            return value
        return normalize_lead_status(value)


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    source: str | None = None
    status: str
    score: int = 0
    card_score: int = 0
    card_level: str = "E"
    industry: str | None = None
    industry_rank: str | None = None
    scene: str | None = None
    budget: str | None = None
    labor_cost: str | None = None
    daily_calls: str | None = None
    leader_owner: str | None = None
    lowest_price: str | None = None
    initiator_department: str | None = None
    competitor: str | None = None
    bidding_type: str | None = None
    has_ai_project: str | None = None
    customer_service_size: str | None = None
    region: str | None = None
    score_detail_json: dict[str, Any] = Field(default_factory=dict)
    owner_id: UUID | None = None
    owner_username: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    owner: UserOut | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class OpportunityReportSummary(BaseModel):
    owner_id: UUID | None = None
    owner_username: str
    total_count: int = 0
    following_count: int = 0
    won_count: int = 0
    high_priority_count: int = 0
    this_week_new: int = 0
    this_month_new: int = 0


class OpportunityReportResponse(BaseModel):
    scope: Literal["me", "user", "all"]
    summary: OpportunityReportSummary
    reports: list[OpportunityReportSummary] = Field(default_factory=list)


class AIParseRequest(BaseModel):
    text: str = Field(..., min_length=5, description="Original transcript or note")
    save_to_opportunity: bool = Field(False, description="Create an opportunity after parsing")


class AIParseResponse(BaseModel):
    customer_name: str
    deal_value: float
    stage: str
    key_needs: list[str]
    next_step: str
    confidence_score: float
    usage: dict[str, Any] | None = None
    opportunity_id: UUID | None = None


class CardEvaluateRequest(BaseModel):
    card_type: Literal["A", "B"]
    company: str | None = Field(None, max_length=255)
    industry: str | None = Field(None, max_length=100)
    opportunity_name: str | None = Field(None, max_length=255)
    amount: float | None = Field(None, ge=0)
    text: str = Field("", max_length=10000)

    @model_validator(mode="after")
    def validate_inputs(self):
        if self.card_type == "A" and not ((self.company or "").strip() or self.text.strip()):
            raise ValueError("A-card evaluation needs a company name or description")
        if self.card_type == "B" and not (
            (self.company or "").strip() or (self.opportunity_name or "").strip() or self.text.strip()
        ):
            raise ValueError("B-card evaluation needs company, opportunity name, or description")
        return self


class CardDimensionScore(BaseModel):
    key: str
    name: str
    score: int
    max_score: int


class CardEvaluateResponse(BaseModel):
    card_type: Literal["A", "B"]
    normalized_score: int
    raw_score: int
    raw_max_score: int
    grade: str
    grade_label: str
    rating_desc: str
    suggestion: str
    dimensions: list[CardDimensionScore]


class CardTranscribeResponse(BaseModel):
    text: str
    duration_hint: str


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    data: list[Any]
