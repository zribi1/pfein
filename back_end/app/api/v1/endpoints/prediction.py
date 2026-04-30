from fastapi import APIRouter, Depends

from app.schemas.prediction import PredictRequest, PredictResponse
from app.services.prediction_service import PredictionService

router = APIRouter()


def get_service() -> PredictionService:
    return PredictionService()


@router.post("", response_model=PredictResponse)
async def predict(
    payload: PredictRequest,
    service: PredictionService = Depends(get_service),
) -> PredictResponse:
    return await service.predict(payload)
