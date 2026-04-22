"""
Opportunity API routes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import apply_data_scope, can_edit_owned_resource, get_current_user
from app.db.session import get_db
from app.models import Opportunity, User
from app.schemas import (
    MessageResponse,
    OpportunityCreate,
    OpportunityOut,
    OpportunityUpdate,
    PaginatedResponse,
    StageMoveRequest,
)
from app.services.crm_rules_service import (
    DEFAULT_OPPORTUNITY_STAGE,
    STAGE_DEFAULT_PROBABILITY,
    STAGE_ORDER,
    WON_STAGE,
    LOST_STAGE,
    derive_opportunity_status,
    normalize_opportunity_stage,
    status_to_active,
)
from app.services.scoring_service import SCORING_FIELD_KEYS, calculate_card_score

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _opportunity_dimensions_from_model(opportunity: Opportunity) -> dict[str, str | None]:
    return {field_name: getattr(opportunity, field_name) for field_name in SCORING_FIELD_KEYS}


def _sync_stage_state(
    opportunity: Opportunity,
    next_stage: str,
    changed_at: datetime,
    *,
    override_closed_at: bool = False,
    override_probability: int | None = None,
):
    normalized_stage = normalize_opportunity_stage(next_stage)
    stage_changed = opportunity.stage != normalized_stage
    history = list(opportunity.stage_history or [])

    if stage_changed and history:
        last = history[-1]
        if "exited_at" not in last:
            entered_at = _parse_iso_datetime(last.get("entered_at"))
            last["exited_at"] = changed_at.isoformat()
            last["days"] = max(0, (changed_at - entered_at).days) if entered_at else 0

    if stage_changed or not history:
        history.append({"stage": normalized_stage, "entered_at": changed_at.isoformat()})

    opportunity.stage_history = history
    opportunity.stage = normalized_stage
    opportunity.probability = (
        override_probability
        if override_probability is not None
        else STAGE_DEFAULT_PROBABILITY.get(normalized_stage, STAGE_DEFAULT_PROBABILITY[DEFAULT_OPPORTUNITY_STAGE])
    )

    if normalized_stage in {WON_STAGE, LOST_STAGE}:
        if override_closed_at or opportunity.closed_at is None or stage_changed:
            opportunity.closed_at = changed_at
    elif stage_changed:
        opportunity.closed_at = None


@router.get("", response_model=PaginatedResponse, summary="Opportunity list")
async def list_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    stage: Optional[str] = None,
    status: Optional[str] = None,
    owner_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Opportunity).options(selectinload(Opportunity.owner))
    query = apply_data_scope(query, Opportunity, current_user)

    if stage:
        query = query.where(Opportunity.stage == normalize_opportunity_stage(stage))
    if status:
        query = query.where(Opportunity.status == str(status).strip().lower())
    if owner_id:
        query = query.where(Opportunity.owner_id == str(owner_id))

    total_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_query)).scalar() or 0

    result = await db.execute(
        query.order_by(Opportunity.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    opportunities = result.scalars().all()

    return PaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        data=[OpportunityOut.model_validate(item) for item in opportunities],
    )


@router.get("/funnel", summary="Opportunity funnel summary")
async def funnel_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(
        Opportunity.stage,
        func.count(Opportunity.id).label("count"),
        func.coalesce(func.sum(Opportunity.amount), 0).label("total_amount"),
        func.avg(Opportunity.probability).label("avg_prob"),
    )
    query = apply_data_scope(query, Opportunity, current_user).group_by(Opportunity.stage)

    result = await db.execute(query)
    rows = result.all()
    grouped = {
        row.stage: {
            "count": row.count,
            "total_amount": float(row.total_amount),
            "avg_prob": float(row.avg_prob or 0),
        }
        for row in rows
    }

    return {
        "funnel": [
            {
                "stage": stage_name,
                "count": grouped.get(stage_name, {}).get("count", 0),
                "total_amount": grouped.get(stage_name, {}).get("total_amount", 0),
                "avg_prob": grouped.get(stage_name, {}).get("avg_prob", 0),
            }
            for stage_name in STAGE_ORDER
        ]
    }


@router.post("", response_model=OpportunityOut, status_code=201, summary="Create opportunity")
async def create_opportunity(
    payload: OpportunityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = payload.model_dump(exclude_unset=True)
    scoring = calculate_card_score(data)
    now = datetime.now(timezone.utc)
    stage = normalize_opportunity_stage(data.get("stage"))
    status = str(data.get("status") or "new").strip().lower()
    if status != "archived":
        status = derive_opportunity_status(stage, status)

    opportunity = Opportunity(
        name=data["name"],
        account_id=str(data["account_id"]) if data.get("account_id") else None,
        contact_id=str(data["contact_id"]) if data.get("contact_id") else None,
        owner_id=current_user.id,
        amount=data.get("amount"),
        close_date=data.get("close_date"),
        source=data.get("source"),
        status=status,
        is_active=status_to_active(status),
        card_score=scoring.total_score,
        card_level=scoring.card_level,
        score_detail_json=scoring.detail,
        ai_confidence=data.get("ai_confidence"),
        ai_raw_text=data.get("ai_raw_text"),
        ai_extracted=data.get("ai_extracted") or {},
        custom_fields=data.get("custom_fields") or {},
        **scoring.dimensions,
    )
    _sync_stage_state(opportunity, stage, now, override_probability=data.get("probability"))
    db.add(opportunity)
    await db.commit()
    await db.refresh(opportunity)
    await db.refresh(opportunity, ["owner"])
    return OpportunityOut.model_validate(opportunity)


@router.patch("/{opp_id}", response_model=OpportunityOut, summary="Update opportunity")
async def update_opportunity(
    opp_id: UUID,
    payload: OpportunityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = await _get_opp_or_403(opp_id, db, current_user)
    data = payload.model_dump(exclude_unset=True)
    custom_fields = data.pop("custom_fields", None)

    for field_name in ("name", "amount", "close_date", "source"):
        if field_name in data:
            setattr(opportunity, field_name, data[field_name])

    next_stage = data.get("stage", opportunity.stage)
    next_status = data.get("status", opportunity.status)
    if str(next_status or "").strip().lower() != "archived":
        next_status = derive_opportunity_status(next_stage, next_status)

    dimensions = _opportunity_dimensions_from_model(opportunity)
    for field_name in SCORING_FIELD_KEYS:
        if field_name in data:
            dimensions[field_name] = data[field_name]

    scoring = calculate_card_score(dimensions)
    for field_name, value in scoring.dimensions.items():
        setattr(opportunity, field_name, value)

    opportunity.card_score = scoring.total_score
    opportunity.card_level = scoring.card_level
    opportunity.score_detail_json = scoring.detail
    opportunity.status = str(next_status).strip().lower()
    opportunity.is_active = status_to_active(opportunity.status)

    if "stage" in data:
        _sync_stage_state(
            opportunity,
            next_stage,
            datetime.now(timezone.utc),
            override_probability=data.get("probability"),
        )
    elif "probability" in data:
        opportunity.probability = data["probability"]

    if custom_fields is not None:
        opportunity.custom_fields = {**(opportunity.custom_fields or {}), **custom_fields}

    await db.commit()
    await db.refresh(opportunity)
    await db.refresh(opportunity, ["owner"])
    return OpportunityOut.model_validate(opportunity)


@router.patch("/{opp_id}/stage", response_model=OpportunityOut, summary="Move opportunity stage")
async def move_stage(
    opp_id: UUID,
    payload: StageMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = await _get_opp_or_403(opp_id, db, current_user)
    _sync_stage_state(opportunity, payload.stage, datetime.now(timezone.utc), override_closed_at=True)
    if opportunity.status != "archived":
        opportunity.status = derive_opportunity_status(opportunity.stage, opportunity.status)
        opportunity.is_active = status_to_active(opportunity.status)

    await db.commit()
    await db.refresh(opportunity)
    await db.refresh(opportunity, ["owner"])
    return OpportunityOut.model_validate(opportunity)


@router.delete("/{opp_id}", response_model=MessageResponse, summary="Delete opportunity")
async def delete_opportunity(
    opp_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunity = await _get_opp_or_403(opp_id, db, current_user)
    await db.delete(opportunity)
    await db.commit()
    return MessageResponse(message="商机已删除")


async def _get_opp_or_403(opp_id: UUID, db: AsyncSession, current_user: User) -> Opportunity:
    result = await db.execute(
        select(Opportunity).where(Opportunity.id == str(opp_id)).options(selectinload(Opportunity.owner))
    )
    opportunity = result.scalar_one_or_none()
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if not can_edit_owned_resource(current_user, opportunity.owner_id):
        raise HTTPException(status_code=403, detail="You cannot modify another user's opportunity")
    return opportunity
