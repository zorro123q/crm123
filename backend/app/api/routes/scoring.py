"""
Scoring metadata routes.
"""

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models import User
from app.services.scoring_service import scoring_options_payload

router = APIRouter(prefix="/api/scoring", tags=["scoring"])


@router.get("/options", summary="Scoring field options")
async def scoring_options(_: User = Depends(get_current_user)):
    return {"fields": scoring_options_payload()}
