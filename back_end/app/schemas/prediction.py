from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    keywords: list[str] = Field(..., min_length=1)
    top_n: int = 10


class CompanyPrediction(BaseModel):
    siren: str
    denomination: str
    prediction_modele: int
    probabilite_cessation: float


class PredictResponse(BaseModel):
    keywords: list[str]
    nb_entreprises_trouvees: int
    resultats: list[CompanyPrediction]
