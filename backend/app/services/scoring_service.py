"""
线索和商机共用的评分规则。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCORING_FIELDS: dict[str, dict[str, Any]] = {
    "industry": {
        "label": "行业",
        "options": {
            "finance": {"label": "金融", "score": 5},
            "insurance": {"label": "保险", "score": 5},
            "logistics": {"label": "物流", "score": 4},
            "manufacturing": {"label": "制造业", "score": 4},
            "retail": {"label": "零售", "score": 4},
            "other_large_customer_service": {"label": "其他大客服规模行业", "score": 3},
            "other": {"label": "其他", "score": 0},
        },
    },
    "industry_rank": {
        "label": "行业排名",
        "options": {
            "top_1_10": {"label": "1 到 10 名", "score": 5},
            "top_11_20": {"label": "11 到 20 名", "score": 3},
            "top_21_30": {"label": "21 到 30 名", "score": 2},
            "above_30": {"label": "30 名以后", "score": 1},
        },
    },
    "scene": {
        "label": "场景",
        "options": {
            "logistics_outbound_calls": {"label": "物流外呼", "score": 5},
            "financial_marketing": {"label": "金融营销", "score": 5},
            "intelligent_callback": {"label": "智能回呼", "score": 10},
            "financial_collection": {"label": "金融催收", "score": 10},
            "insurance_marketing": {"label": "保险营销", "score": 10},
            "voice_portal": {"label": "语音门户", "score": 10},
            "appliance_installation_repair_scheduling": {"label": "家电安装维修预约", "score": 10},
            "insurance_claim_reporting": {"label": "保险报案", "score": 10},
            "large_model_application": {"label": "大模型应用", "score": 5},
            "capacity_expansion": {"label": "扩容", "score": 5},
            "similar_cross_industry": {"label": "异行业相似场景", "score": 5},
            "other": {"label": "其他", "score": 1},
        },
    },
    "budget": {
        "label": "预算",
        "options": {
            "above_3_million": {"label": "300 万以上", "score": 5},
            "between_2_and_3_million": {"label": "200 到 300 万", "score": 3},
            "around_1_million": {"label": "100 万左右", "score": 2},
            "between_0_5_and_1_million": {"label": "50 到 100 万", "score": 1},
            "below_0_5_million": {"label": "50 万以下", "score": 0},
        },
    },
    "labor_cost": {
        "label": "人力成本",
        "options": {
            "above_6000": {"label": "6000 以上", "score": 5},
            "between_5000_and_6000": {"label": "5000 到 6000", "score": 4},
            "between_4000_and_5000": {"label": "4000 到 5000", "score": 3},
            "between_3000_and_4000": {"label": "4000 以下", "score": 2},
            "between_2000_and_3000": {"label": "3000 以下", "score": 1},
            "below_2000": {"label": "2000 以下", "score": 0},
        },
    },
    "daily_calls": {
        "label": "人均日呼量",
        "options": {
            "below_60": {"label": "60 通以下/天", "score": 4},
            "between_60_and_80": {"label": "60 到 80 通/天", "score": 3},
            "between_80_and_100": {"label": "80 到 100 通/天", "score": 2},
            "above_100": {"label": "100 通以上/天", "score": 1},
        },
    },
    "leader_owner": {
        "label": "负责人分管",
        "options": {
            "business_and_technology": {"label": "同时分管业务和技术", "score": 5},
            "business": {"label": "分管业务", "score": 3},
            "technology": {"label": "分管技术", "score": 1},
        },
    },
    "lowest_price": {
        "label": "是否最低价",
        "options": {
            "no": {"label": "否", "score": 3},
            "yes": {"label": "是", "score": 1},
        },
    },
    "initiator_department": {
        "label": "发起部门",
        "options": {
            "business": {"label": "业务部门", "score": 5},
            "technology": {"label": "技术部门", "score": 2},
        },
    },
    "competitor": {
        "label": "竞争情况",
        "options": {
            "no_competitor": {"label": "无竞争对手", "score": 4},
            "competitor_without_bat": {"label": "有竞争对手，不含 BAT", "score": 2},
            "competitor_with_bat": {"label": "有竞争对手，含 BAT", "score": 1},
            "more_than_5_competitors": {"label": "竞争对手超过 5 家", "score": 0},
        },
    },
    "bidding_type": {
        "label": "招采方式",
        "options": {
            "single_source_procurement": {"label": "单一来源采购", "score": 30},
            "invitational_controllable": {"label": "邀标，可控", "score": 20},
            "invitational_uncontrollable": {"label": "邀标，不可控", "score": 5},
            "public_bidding": {"label": "公开招标", "score": 0},
        },
    },
    "has_ai_project": {
        "label": "是否有 AI 项目",
        "options": {
            "yes": {"label": "是", "score": 4},
            "no": {"label": "否", "score": 1},
        },
    },
    "customer_service_size": {
        "label": "客服规模",
        "options": {
            "above_500": {"label": "500 席以上", "score": 5},
            "between_300_and_500": {"label": "300 到 500 席", "score": 3},
            "between_100_and_300": {"label": "100 到 300 席", "score": 2},
            "below_100": {"label": "100 席以下", "score": 1},
        },
    },
    "region": {
        "label": "区域",
        "options": {
            "bj_sh_gz_sz": {"label": "北上广深", "score": 10},
            "tier_1": {"label": "新一线城市", "score": 8},
            "tier_2": {"label": "二线城市", "score": 5},
            "tier_3": {"label": "三线城市", "score": 3},
            "tier_4": {"label": "四线城市", "score": 1},
        },
    },
}

SCORING_FIELD_KEYS = tuple(SCORING_FIELDS.keys())


@dataclass(slots=True)
class ScoreResult:
    dimensions: dict[str, str | None]
    detail: dict[str, dict[str, Any]]
    total_score: int
    card_level: str


def is_valid_option(field_name: str, value: str | None) -> bool:
    if value in (None, ""):
        return True
    field = SCORING_FIELDS.get(field_name)
    return bool(field and value in field["options"])


def normalize_scoring_dimensions(payload: dict[str, Any]) -> dict[str, str | None]:
    dimensions: dict[str, str | None] = {}
    for field_name in SCORING_FIELD_KEYS:
        value = payload.get(field_name)
        normalized = str(value).strip() if value is not None else None
        if normalized == "":
            normalized = None
        if not is_valid_option(field_name, normalized):
            raise ValueError(f"{field_name} 的评分选项不合法: {value}")
        dimensions[field_name] = normalized
    return dimensions


def calculate_card_level(score: int) -> str:
    if score < 20:
        return "E"
    if score < 40:
        return "D"
    if score < 60:
        return "C"
    if score < 70:
        return "B"
    return "A"


def calculate_card_score(payload: dict[str, Any]) -> ScoreResult:
    dimensions = normalize_scoring_dimensions(payload)
    detail: dict[str, dict[str, Any]] = {}
    total_score = 0

    for field_name in SCORING_FIELD_KEYS:
        selected_value = dimensions.get(field_name)
        field_meta = SCORING_FIELDS[field_name]
        option_meta = field_meta["options"].get(selected_value)
        score = int(option_meta["score"]) if option_meta else 0
        total_score += score
        detail[field_name] = {
            "label": field_meta["label"],
            "value": selected_value,
            "value_label": option_meta["label"] if option_meta else None,
            "score": score,
        }

    return ScoreResult(
        dimensions=dimensions,
        detail=detail,
        total_score=total_score,
        card_level=calculate_card_level(total_score),
    )


def scoring_options_payload() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field_name, field_meta in SCORING_FIELDS.items():
        rows.append(
            {
                "field": field_name,
                "label": field_meta["label"],
                "options": [
                    {
                        "value": option_value,
                        "label": option_meta["label"],
                        "score": option_meta["score"],
                    }
                    for option_value, option_meta in field_meta["options"].items()
                ],
            }
        )
    return rows
