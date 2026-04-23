import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.api.routes.card_evaluations import evaluate_card_view
from app.schemas import CardEvaluateRequest, ScoringDimensionsInput
from app.services.card_evaluation_service import merge_dimensions


class MergeDimensionsTests(unittest.TestCase):
    def test_manual_values_override_ai_and_ai_fills_gaps(self):
        merged, sources = merge_dimensions(
            ai_dimensions={
                "budget": "above_3_million",
                "region": "tier_2",
            },
            manual_dimensions={
                "budget": "around_1_million",
                "industry": "insurance",
            },
        )

        self.assertEqual(merged["budget"], "around_1_million")
        self.assertEqual(merged["region"], "tier_2")
        self.assertEqual(merged["industry"], "insurance")
        self.assertEqual(sources["budget"], "manual")
        self.assertEqual(sources["region"], "ai")
        self.assertEqual(sources["industry"], "manual")
        self.assertEqual(sources["scene"], "none")


class CardEvaluateRequestValidationTests(unittest.TestCase):
    def test_manual_mode_requires_manual_dimensions(self):
        with self.assertRaises(ValidationError):
            CardEvaluateRequest(card_type="A", analysis_mode="manual")

    def test_hybrid_mode_requires_text_when_ai_dimensions_missing(self):
        with self.assertRaises(ValidationError):
            CardEvaluateRequest(
                card_type="B",
                analysis_mode="hybrid",
                manual_dimensions=ScoringDimensionsInput(industry="insurance"),
            )


class CardEvaluationRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_mode_skips_ai_and_scores_manual_dimensions(self):
        payload = CardEvaluateRequest(
            card_type="A",
            analysis_mode="manual",
            manual_dimensions=ScoringDimensionsInput(industry="insurance"),
        )

        with patch("app.api.routes.card_evaluations.extract_scoring_dimensions_from_text", new=AsyncMock()) as mocked:
            result = await evaluate_card_view(payload)

        self.assertEqual(result.raw_score, 5)
        self.assertEqual(result.normalized_score, 5)
        self.assertEqual(result.merged_dimensions.industry, "insurance")
        self.assertEqual(result.dimensions[0].source, "manual")
        mocked.assert_not_awaited()

    async def test_ai_mode_reuses_cached_ai_dimensions(self):
        payload = CardEvaluateRequest(
            card_type="A",
            analysis_mode="ai",
            text="cached text",
            ai_dimensions=ScoringDimensionsInput(industry="insurance"),
        )

        with patch("app.api.routes.card_evaluations.extract_scoring_dimensions_from_text", new=AsyncMock()) as mocked:
            result = await evaluate_card_view(payload)

        self.assertEqual(result.ai_dimensions.industry, "insurance")
        self.assertEqual(result.merged_dimensions.industry, "insurance")
        mocked.assert_not_awaited()

    async def test_hybrid_mode_merges_manual_and_ai_dimensions(self):
        payload = CardEvaluateRequest(
            card_type="B",
            analysis_mode="hybrid",
            text="fresh text",
            manual_dimensions=ScoringDimensionsInput(budget="around_1_million"),
        )

        with patch(
            "app.api.routes.card_evaluations.extract_scoring_dimensions_from_text",
            new=AsyncMock(
                return_value={
                    "industry": None,
                    "industry_rank": None,
                    "scene": None,
                    "budget": "above_3_million",
                    "labor_cost": None,
                    "daily_calls": None,
                    "leader_owner": None,
                    "lowest_price": None,
                    "initiator_department": None,
                    "competitor": None,
                    "bidding_type": None,
                    "has_ai_project": None,
                    "customer_service_size": None,
                    "region": "tier_1",
                }
            ),
        ) as mocked:
            result = await evaluate_card_view(payload)

        self.assertEqual(result.merged_dimensions.budget, "around_1_million")
        self.assertEqual(result.merged_dimensions.region, "tier_1")
        detail_by_key = {item.key: item for item in result.dimensions}
        self.assertEqual(detail_by_key["budget"].source, "manual")
        self.assertEqual(detail_by_key["region"].source, "ai")
        mocked.assert_awaited_once()

    async def test_ai_extraction_failure_returns_502(self):
        payload = CardEvaluateRequest(
            card_type="A",
            analysis_mode="ai",
            text="need extraction",
        )

        with patch(
            "app.api.routes.card_evaluations.extract_scoring_dimensions_from_text",
            new=AsyncMock(side_effect=RuntimeError("invalid enum")),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await evaluate_card_view(payload)

        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.detail, "invalid enum")


if __name__ == "__main__":
    unittest.main()
