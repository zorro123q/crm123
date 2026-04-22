"""
Database-backed analytics for dashboard and funnel pages.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import apply_data_scope, get_current_user
from app.db.session import get_db
from app.models import Lead, Opportunity, User
from app.services.crm_rules_service import (
    DEFAULT_OPPORTUNITY_STAGE,
    LOST_STAGE,
    NEGOTIATION_STAGE,
    QUOTE_STAGE,
    WON_STAGE,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ACTIVE_OPPORTUNITY_STAGES = (DEFAULT_OPPORTUNITY_STAGE, QUOTE_STAGE, NEGOTIATION_STAGE)
DASHBOARD_FUNNEL_STAGES = (DEFAULT_OPPORTUNITY_STAGE, QUOTE_STAGE, NEGOTIATION_STAGE, WON_STAGE, LOST_STAGE)
CUSTOMER_FUNNEL_STAGES = (DEFAULT_OPPORTUNITY_STAGE, QUOTE_STAGE, NEGOTIATION_STAGE, WON_STAGE)

OLD_CUSTOMER_VALUES = {
    "\u8001\u5ba2\u6237",
    "\u8001\u5ba2\u6237\u65b0\u90e8\u95e8",
    "old",
}
NEW_CUSTOMER_VALUES = {
    "\u65b0\u5ba2\u6237",
    "new",
}
OLD_CUSTOMER_VALUES_NORMALIZED = {item.lower() for item in OLD_CUSTOMER_VALUES}
NEW_CUSTOMER_VALUES_NORMALIZED = {item.lower() for item in NEW_CUSTOMER_VALUES}


def start_of_month(day: date) -> date:
    return day.replace(day=1)


def end_of_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1) - timedelta(days=1)
    return date(day.year, day.month + 1, 1) - timedelta(days=1)


def start_of_quarter(day: date) -> date:
    month = ((day.month - 1) // 3) * 3 + 1
    return date(day.year, month, 1)


def end_of_quarter(day: date) -> date:
    start = start_of_quarter(day)
    if start.month == 10:
        return date(start.year + 1, 1, 1) - timedelta(days=1)
    return date(start.year, start.month + 3, 1) - timedelta(days=1)


def ensure_date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def in_range(value, start: date, end: date) -> bool:
    current = ensure_date(value)
    return current is not None and start <= current <= end


def normalize_customer_type(value: str | None) -> str | None:
    raw = str(value or "").strip().lower()
    if raw in OLD_CUSTOMER_VALUES_NORMALIZED:
        return "old"
    if raw in NEW_CUSTOMER_VALUES_NORMALIZED:
        return "new"
    return None


def classify_opportunity(opportunity: Opportunity) -> str | None:
    custom_fields = opportunity.custom_fields or {}
    return normalize_customer_type(custom_fields.get("customer_type"))


def classify_lead(lead: Lead) -> str | None:
    custom_fields = lead.custom_fields or {}
    return normalize_customer_type(custom_fields.get("customer_type"))


def amount_of(opportunity: Opportunity) -> float:
    return float(opportunity.amount or 0)


def probability_of(opportunity: Opportunity) -> int:
    return int(opportunity.probability or 0)


def closed_reference_date(opportunity: Opportunity):
    return opportunity.closed_at or opportunity.close_date or opportunity.updated_at or opportunity.created_at


def month_bucket_start(day: date, offset: int) -> date:
    month = day.month + offset
    year = day.year
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


@router.get("/overview", summary="Dashboard and funnel analytics")
async def analytics_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opportunities_query = select(Opportunity).options(selectinload(Opportunity.owner))
    opportunities_query = apply_data_scope(opportunities_query, Opportunity, current_user)
    opportunities_result = await db.execute(opportunities_query.order_by(Opportunity.updated_at.desc()))
    opportunities = opportunities_result.scalars().all()

    leads_query = select(Lead).options(selectinload(Lead.owner))
    leads_query = apply_data_scope(leads_query, Lead, current_user)
    leads_result = await db.execute(leads_query.order_by(Lead.updated_at.desc()))
    leads = leads_result.scalars().all()

    today = date.today()
    month_start = start_of_month(today)
    month_end = end_of_month(today)
    quarter_start = start_of_quarter(today)
    quarter_end = end_of_quarter(today)

    active_opportunities = [item for item in opportunities if item.stage in ACTIVE_OPPORTUNITY_STAGES]
    quarter_pipeline = [
        item for item in active_opportunities if in_range(item.close_date or item.created_at, quarter_start, quarter_end)
    ]
    won_this_month = [
        item for item in opportunities if item.stage == WON_STAGE and in_range(closed_reference_date(item), month_start, month_end)
    ]

    dashboard_funnel = []
    for stage_name in DASHBOARD_FUNNEL_STAGES:
        stage_items = [item for item in opportunities if item.stage == stage_name]
        stage_amount = sum(amount_of(item) for item in stage_items)
        stage_probabilities = [probability_of(item) for item in stage_items if item.probability is not None]
        dashboard_funnel.append(
            {
                "stage": stage_name,
                "count": len(stage_items),
                "total_amount": round(stage_amount, 2),
                "avg_probability": round(sum(stage_probabilities) / len(stage_probabilities), 2)
                if stage_probabilities
                else 0,
            }
        )

    monthly_performance = []
    for offset in (-2, -1, 0):
        bucket_start = month_bucket_start(today, offset)
        bucket_end = end_of_month(bucket_start)
        won_amount = sum(
            amount_of(item)
            for item in opportunities
            if item.stage == WON_STAGE and in_range(closed_reference_date(item), bucket_start, bucket_end)
        )
        pipeline_amount = sum(
            amount_of(item)
            for item in opportunities
            if item.stage in ACTIVE_OPPORTUNITY_STAGES and in_range(item.created_at, bucket_start, bucket_end)
        )
        monthly_performance.append(
            {
                "label": f"{bucket_start.year}-{bucket_start.month:02d}",
                "won_amount": round(won_amount, 2),
                "pipeline_amount": round(pipeline_amount, 2),
            }
        )

    owner_amounts: dict[str, float] = defaultdict(float)
    for item in won_this_month:
        owner_name = item.owner.username if item.owner else "Unassigned"
        owner_amounts[owner_name] += amount_of(item)
    owner_ranking = [
        {"owner": owner_name, "won_amount": round(amount, 2)}
        for owner_name, amount in sorted(owner_amounts.items(), key=lambda pair: pair[1], reverse=True)
    ]

    recent_items = []
    for lead in leads[:5]:
        recent_items.append(
            {
                "type": "lead",
                "title": lead.name,
                "subtitle": f"Status: {lead.status}",
                "timestamp": lead.updated_at.isoformat() if lead.updated_at else None,
            }
        )
    for opportunity in opportunities[:5]:
        recent_items.append(
            {
                "type": "opportunity",
                "title": opportunity.name,
                "subtitle": f"Stage: {opportunity.stage}",
                "timestamp": opportunity.updated_at.isoformat() if opportunity.updated_at else None,
            }
        )
    recent_activity = sorted(
        recent_items,
        key=lambda item: item["timestamp"] or "",
        reverse=True,
    )[:5]

    quarter_leads = [lead for lead in leads if in_range(lead.created_at, quarter_start, quarter_end)]
    old_leads = [lead for lead in quarter_leads if classify_lead(lead) == "old"]
    new_leads = [lead for lead in quarter_leads if classify_lead(lead) == "new"]

    quarter_won_opportunities = [
        item
        for item in opportunities
        if item.stage == WON_STAGE and in_range(closed_reference_date(item), quarter_start, quarter_end)
    ]
    old_signed = [item for item in quarter_won_opportunities if classify_opportunity(item) == "old"]
    new_signed = [item for item in quarter_won_opportunities if classify_opportunity(item) == "new"]

    quarter_customer_opportunities = [
        item for item in opportunities if in_range(item.created_at, quarter_start, quarter_end) and classify_opportunity(item)
    ]
    old_customer_opportunities = [item for item in quarter_customer_opportunities if classify_opportunity(item) == "old"]
    new_customer_opportunities = [item for item in quarter_customer_opportunities if classify_opportunity(item) == "new"]

    def build_customer_funnel(items: list[Opportunity]) -> list[dict[str, float | int | str]]:
        rows = []
        for stage_name in CUSTOMER_FUNNEL_STAGES:
            stage_items = [item for item in items if item.stage == stage_name]
            total_amount = sum(amount_of(item) for item in stage_items)
            rows.append(
                {
                    "stage": stage_name,
                    "count": len(stage_items),
                    "amount": round(total_amount, 2),
                    "avg_amount": round(total_amount / len(stage_items), 2) if stage_items else 0,
                }
            )
        return rows

    old_customer_funnel = build_customer_funnel(old_customer_opportunities)
    new_customer_funnel = build_customer_funnel(new_customer_opportunities)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "periods": {
            "today": today.isoformat(),
            "month_start": month_start.isoformat(),
            "month_end": month_end.isoformat(),
            "quarter_start": quarter_start.isoformat(),
            "quarter_end": quarter_end.isoformat(),
        },
        "dashboard": {
            "total_pipeline_amount_this_quarter": round(sum(amount_of(item) for item in quarter_pipeline), 2),
            "total_won_deals_this_month": len(won_this_month),
            "active_opportunities_count": len(active_opportunities),
            "average_win_rate": round(
                sum(probability_of(item) for item in active_opportunities) / len(active_opportunities), 2
            )
            if active_opportunities
            else 0,
            "funnel_stages": dashboard_funnel,
            "monthly_performance": monthly_performance,
            "owner_ranking_this_month": owner_ranking,
            "recent_activity": recent_activity,
        },
        "customer_funnel": {
            "customer_information_collected_count": len(quarter_leads),
            "old_customer_information_collected_count": len(old_leads),
            "old_customer_signed_payment_amount": round(sum(amount_of(item) for item in old_signed), 2),
            "new_customer_information_collected_count": len(new_leads),
            "new_customer_signed_payment_amount": round(sum(amount_of(item) for item in new_signed), 2),
            "unclassified_information_count": len(quarter_leads) - len(old_leads) - len(new_leads),
            "unclassified_signed_payment_amount": round(
                sum(amount_of(item) for item in quarter_won_opportunities)
                - sum(amount_of(item) for item in old_signed)
                - sum(amount_of(item) for item in new_signed),
                2,
            ),
            "old_customer_stages": old_customer_funnel,
            "new_customer_stages": new_customer_funnel,
        },
    }
