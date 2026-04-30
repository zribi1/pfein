from app.ml.loader import ml_registry
from app.schemas.prediction import PredictRequest, PredictResponse


class PredictionService:
    async def predict(self, payload: PredictRequest) -> PredictResponse:
        model = ml_registry.get("default")
        # TODO: implement the real feature-extraction + model.predict_proba pipeline
        _ = model
        return PredictResponse(
            keywords=payload.keywords,
            nb_entreprises_trouvees=0,
            resultats=[],
        )
