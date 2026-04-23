from __future__ import annotations

from typing import Any, Mapping

from app.services.scoring_service import SCORING_FIELD_KEYS, SCORING_FIELDS, calculate_card_score, normalize_scoring_dimensions


CARD_COPY: dict[str, dict[str, dict[str, str]]] = {
    "A": {
        "A": {
            "label": "A卡 · 高意向客户",
            "desc": "正式评分达到 A 级，客户意向和客户价值较高，建议立即安排关键人深度沟通。",
            "suggestion": "优先推进需求澄清、预算确认和采购路径确认，保持高频跟进。",
        },
        "B": {
            "label": "A卡 · 值得重点跟进",
            "desc": "正式评分达到 B 级，客户价值较好，建议尽快补齐剩余关键信息。",
            "suggestion": "围绕场景、预算、负责人和区域继续补充信息，维持稳定跟进节奏。",
        },
        "C": {
            "label": "A卡 · 持续观察",
            "desc": "正式评分达到 C 级，客户基础条件一般，需要继续判断真实意向和价值。",
            "suggestion": "先确认场景匹配度和预算区间，再决定是否投入更多资源。",
        },
        "D": {
            "label": "A卡 · 谨慎投入",
            "desc": "正式评分达到 D 级，当前客户价值偏弱，不宜过早投入过多精力。",
            "suggestion": "保持基础联系，等待预算、采购方式或需求成熟后再加大推进力度。",
        },
        "E": {
            "label": "A卡 · 暂不优先",
            "desc": "正式评分达到 E 级，当前客户价值有限，暂不建议作为重点对象推进。",
            "suggestion": "保留基础触达即可，将资源优先分配给更高确定性的客户。",
        },
    },
    "B": {
        "A": {
            "label": "B卡 · 高价值商机",
            "desc": "正式评分达到 A 级，商机质量高，具备较强推进价值和成交潜力。",
            "suggestion": "尽快锁定下一步商务动作，推动方案、决策链和采购流程并行推进。",
        },
        "B": {
            "label": "B卡 · 优先商机",
            "desc": "正式评分达到 B 级，商机条件较好，适合持续投入推进。",
            "suggestion": "补齐竞争态势、负责人和预算细节，推动客户进入下一决策阶段。",
        },
        "C": {
            "label": "B卡 · 中等商机",
            "desc": "正式评分达到 C 级，商机基础一般，需要继续验证推进条件。",
            "suggestion": "重点确认预算、采购方式和客户侧牵头部门，避免过早重投入。",
        },
        "D": {
            "label": "B卡 · 弱商机",
            "desc": "正式评分达到 D 级，当前商机不够稳固，需要谨慎评估投入产出。",
            "suggestion": "控制推进成本，优先核实采购真实性和项目优先级是否足够明确。",
        },
        "E": {
            "label": "B卡 · 暂不推进",
            "desc": "正式评分达到 E 级，当前商机价值偏低，短期内不建议作为重点项目。",
            "suggestion": "先保持观察，等待明确预算、场景或采购信号后再决定是否重启推进。",
        },
    },
}

SOURCE_MANUAL = "manual"
SOURCE_AI = "ai"
SOURCE_NONE = "none"


def empty_dimensions() -> dict[str, str | None]:
    return {field_name: None for field_name in SCORING_FIELD_KEYS}


def normalize_dimensions(dimensions: Mapping[str, Any] | None) -> dict[str, str | None]:
    if dimensions is None:
        return empty_dimensions()
    return normalize_scoring_dimensions(dict(dimensions))


def merge_dimensions(
    ai_dimensions: Mapping[str, Any] | None,
    manual_dimensions: Mapping[str, Any] | None,
) -> tuple[dict[str, str | None], dict[str, str]]:
    normalized_ai = normalize_dimensions(ai_dimensions)
    normalized_manual = normalize_dimensions(manual_dimensions)
    merged: dict[str, str | None] = {}
    sources: dict[str, str] = {}

    for field_name in SCORING_FIELD_KEYS:
        manual_value = normalized_manual.get(field_name)
        ai_value = normalized_ai.get(field_name)
        if manual_value is not None:
            merged[field_name] = manual_value
            sources[field_name] = SOURCE_MANUAL
        elif ai_value is not None:
            merged[field_name] = ai_value
            sources[field_name] = SOURCE_AI
        else:
            merged[field_name] = None
            sources[field_name] = SOURCE_NONE

    return merged, sources


def evaluate_card(
    card_type: str,
    *,
    ai_dimensions: Mapping[str, Any] | None = None,
    manual_dimensions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if card_type not in CARD_COPY:
        raise ValueError("Unsupported card type")

    normalized_ai = normalize_dimensions(ai_dimensions) if ai_dimensions is not None else None
    normalized_manual = normalize_dimensions(manual_dimensions) if manual_dimensions is not None else None
    merged_dimensions, sources = merge_dimensions(normalized_ai, normalized_manual)
    scoring = calculate_card_score(merged_dimensions)
    copy = CARD_COPY[card_type][scoring.card_level]

    dimensions: list[dict[str, Any]] = []
    for field_name in SCORING_FIELD_KEYS:
        field_meta = SCORING_FIELDS[field_name]
        detail = scoring.detail[field_name]
        max_score = max(int(option_meta["score"]) for option_meta in field_meta["options"].values())
        dimensions.append(
            {
                "key": field_name,
                "name": field_meta["label"],
                "score": int(detail["score"]),
                "max_score": max_score,
                "selected_value": detail["value"],
                "selected_label": detail["value_label"],
                "source": sources[field_name],
            }
        )

    return {
        "card_type": card_type,
        "normalized_score": scoring.total_score,
        "raw_score": scoring.total_score,
        "raw_max_score": 100,
        "grade": scoring.card_level,
        "grade_label": copy["label"],
        "rating_desc": copy["desc"],
        "suggestion": copy["suggestion"],
        "ai_dimensions": normalized_ai,
        "manual_dimensions": normalized_manual,
        "merged_dimensions": merged_dimensions,
        "dimensions": dimensions,
    }
