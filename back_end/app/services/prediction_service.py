from app.ml.loader import ml_registry
from app.core.config import settings
from app.schemas.prediction import (
    CompanyContinuityPredictionResponse,
    PredictRequest,
    PredictResponse,
)


class PredictionService:
    def __init__(self, db=None) -> None:
        self.db = db

    async def predict(self, payload: PredictRequest) -> PredictResponse:
        model = ml_registry.get("default")
        # TODO: implement the real feature-extraction + model.predict_proba pipeline
        _ = model
        return PredictResponse(
            keywords=payload.keywords,
            nb_entreprises_trouvees=0,
            resultats=[],
        )

    async def get_company_continuity_prediction(
        self,
        siren: str,
    ) -> CompanyContinuityPredictionResponse | None:
        if self.db is None:
            return None

        doc = await self.db[settings.PREDICTION_RESULTS_COLLECTION].find_one(
            {
                "siren": siren,
                "target": "continuity_risk_12m",
                "horizon_months": 12,
            },
            {"_id": 0},
        )
        if doc is None:
            return None
        return CompanyContinuityPredictionResponse(**doc)
