"""
Runtime schema patching for local development environments.
"""

from __future__ import annotations

from sqlalchemy import text

from app.db.session import engine
from app.services.crm_rules_service import DEFAULT_OPPORTUNITY_STAGE


LEAD_COLUMN_DEFINITIONS = {
    "card_score": "INT NOT NULL DEFAULT 0 AFTER score",
    "card_level": "VARCHAR(1) NOT NULL DEFAULT 'E' AFTER card_score",
    "is_active": "TINYINT(1) NOT NULL DEFAULT 1 AFTER converted_to",
    "industry": "VARCHAR(100) NULL AFTER is_active",
    "industry_rank": "VARCHAR(100) NULL AFTER industry",
    "scene": "VARCHAR(120) NULL AFTER industry_rank",
    "budget": "VARCHAR(100) NULL AFTER scene",
    "labor_cost": "VARCHAR(100) NULL AFTER budget",
    "daily_calls": "VARCHAR(100) NULL AFTER labor_cost",
    "leader_owner": "VARCHAR(100) NULL AFTER daily_calls",
    "lowest_price": "VARCHAR(50) NULL AFTER leader_owner",
    "initiator_department": "VARCHAR(100) NULL AFTER lowest_price",
    "competitor": "VARCHAR(100) NULL AFTER initiator_department",
    "bidding_type": "VARCHAR(100) NULL AFTER competitor",
    "has_ai_project": "VARCHAR(50) NULL AFTER bidding_type",
    "customer_service_size": "VARCHAR(100) NULL AFTER has_ai_project",
    "region": "VARCHAR(100) NULL AFTER customer_service_size",
    "score_detail_json": "JSON NULL AFTER region",
}

OPPORTUNITY_COLUMN_DEFINITIONS = {
    "status": "VARCHAR(50) NOT NULL DEFAULT 'new' AFTER stage",
    "card_score": "INT NOT NULL DEFAULT 0 AFTER source",
    "card_level": "VARCHAR(1) NOT NULL DEFAULT 'E' AFTER card_score",
    "is_active": "TINYINT(1) NOT NULL DEFAULT 1 AFTER card_level",
    "industry": "VARCHAR(100) NULL AFTER is_active",
    "industry_rank": "VARCHAR(100) NULL AFTER industry",
    "scene": "VARCHAR(120) NULL AFTER industry_rank",
    "budget": "VARCHAR(100) NULL AFTER scene",
    "labor_cost": "VARCHAR(100) NULL AFTER budget",
    "daily_calls": "VARCHAR(100) NULL AFTER labor_cost",
    "leader_owner": "VARCHAR(100) NULL AFTER daily_calls",
    "lowest_price": "VARCHAR(50) NULL AFTER leader_owner",
    "initiator_department": "VARCHAR(100) NULL AFTER lowest_price",
    "competitor": "VARCHAR(100) NULL AFTER initiator_department",
    "bidding_type": "VARCHAR(100) NULL AFTER competitor",
    "has_ai_project": "VARCHAR(50) NULL AFTER bidding_type",
    "customer_service_size": "VARCHAR(100) NULL AFTER has_ai_project",
    "region": "VARCHAR(100) NULL AFTER customer_service_size",
    "score_detail_json": "JSON NULL AFTER custom_fields",
}

LEAD_FIXUP_STATEMENTS = [
    """
    UPDATE leads
    SET status = CASE
        WHEN LOWER(status) = 'new' THEN 'new'
        WHEN LOWER(status) IN ('working', 'nurturing', 'follow_up') THEN 'follow_up'
        WHEN LOWER(status) = 'converted' THEN 'converted'
        WHEN LOWER(status) IN ('disqualified', 'invalid') THEN 'invalid'
        WHEN LOWER(status) = 'archived' THEN 'archived'
        ELSE 'new'
    END
    """,
    """
    UPDATE leads
    SET card_score = COALESCE(score, 0)
    WHERE card_score = 0 AND score IS NOT NULL
    """,
    """
    UPDATE leads
    SET card_level = CASE
        WHEN card_score < 20 THEN 'E'
        WHEN card_score < 40 THEN 'D'
        WHEN card_score < 60 THEN 'C'
        WHEN card_score < 70 THEN 'B'
        ELSE 'A'
    END
    """,
    """
    UPDATE leads
    SET is_active = IF(status = 'archived', FALSE, TRUE),
        score_detail_json = COALESCE(score_detail_json, JSON_OBJECT())
    """,
]

OPPORTUNITY_FIXUP_STATEMENTS = [
    """
    UPDATE opportunities
    SET status = CASE
        WHEN LOWER(status) = 'archived' THEN 'archived'
        WHEN COALESCE(probability, 0) >= 100 THEN 'won'
        WHEN COALESCE(probability, 20) = 0 THEN 'lost'
        WHEN COALESCE(probability, 20) > 20 THEN 'follow_up'
        ELSE 'new'
    END
    """,
    """
    UPDATE opportunities
    SET card_level = CASE
        WHEN card_score < 20 THEN 'E'
        WHEN card_score < 40 THEN 'D'
        WHEN card_score < 60 THEN 'C'
        WHEN card_score < 70 THEN 'B'
        ELSE 'A'
    END
    """,
    """
    UPDATE opportunities
    SET is_active = IF(status = 'archived', FALSE, TRUE),
        score_detail_json = COALESCE(score_detail_json, JSON_OBJECT())
    """,
]


async def _show_columns(conn, table_name: str) -> dict[str, str]:
    rows = (await conn.execute(text(f"SHOW COLUMNS FROM {table_name}"))).all()
    return {str(row[0]): str(row[1]).lower() for row in rows}


async def _add_missing_columns(conn, table_name: str, existing: dict[str, str], definitions: dict[str, str]):
    for column_name, definition in definitions.items():
        if column_name not in existing:
            await conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))


async def ensure_runtime_schema():
    async with engine.begin() as conn:
        lead_columns = await _show_columns(conn, "leads")
        if lead_columns.get("status", "").startswith("enum("):
            await conn.execute(text("ALTER TABLE leads MODIFY COLUMN status VARCHAR(50) NOT NULL DEFAULT 'new'"))
        await _add_missing_columns(conn, "leads", lead_columns, LEAD_COLUMN_DEFINITIONS)
        for statement in LEAD_FIXUP_STATEMENTS:
            await conn.execute(text(statement))

        opportunity_columns = await _show_columns(conn, "opportunities")
        await conn.execute(
            text(
                f"ALTER TABLE opportunities MODIFY COLUMN stage VARCHAR(100) "
                f"NOT NULL DEFAULT '{DEFAULT_OPPORTUNITY_STAGE}'"
            )
        )
        await _add_missing_columns(conn, "opportunities", opportunity_columns, OPPORTUNITY_COLUMN_DEFINITIONS)
        for statement in OPPORTUNITY_FIXUP_STATEMENTS:
            await conn.execute(text(statement))
