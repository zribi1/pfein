from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import mongo_db
from app.schemas.prediction import CompanyContinuityPredictionResponse, PredictRequest, PredictResponse
from app.services.prediction_service import PredictionService

router = APIRouter()


def get_service(db: AsyncIOMotorDatabase = Depends(mongo_db)) -> PredictionService:
    return PredictionService(db)


@router.post(
    "",
    response_model=PredictResponse,
    summary="Score one company",
    description=(
        "Runs the continuity-risk prediction service for the company payload you provide. "
        "Use this for ad hoc scoring when you already have the required company features in the request body."
    ),
    response_description="Fresh prediction result for the submitted company payload.",
)
async def predict(
    payload: PredictRequest = Body(
        ...,
        description="Company feature payload used by the prediction service.",
    ),
    service: PredictionService = Depends(get_service),
) -> PredictResponse:
    return await service.predict(payload)


@router.get(
    "/{siren}",
    response_model=CompanyContinuityPredictionResponse,
    summary="Get latest stored company prediction",
    description=(
        "Fetches the latest published 12-month continuity-risk prediction for a SIREN. "
        "Use this endpoint for frontend company pages and dashboards after prediction results have been published."
    ),
    response_description="Stored continuity-risk prediction for the requested SIREN.",
)
async def get_company_prediction(
    siren: str = Path(
        ...,
        description="Nine-digit French company SIREN identifier.",
        min_length=9,
        max_length=9,
        pattern=r"^[0-9]{9}$",
    ),
    service: PredictionService = Depends(get_service),
) -> CompanyContinuityPredictionResponse:
    prediction = await service.get_company_continuity_prediction(siren)
    if prediction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No continuity prediction found for SIREN {siren}",
        )
    return prediction
