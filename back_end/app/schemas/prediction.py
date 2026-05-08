from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any


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


class ExplanationFactor(BaseModel):
    code: str
    label: str
    value: Any = None
    direction: str


class CompanyContinuityPredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    siren: str
    target: str = "continuity_risk_12m"
    horizon_months: int = 12
    model_version: str | None = None
    prediction_year: int | None = None
    probability: float | None = None
    score_percent: float | None = None
    risk_bucket: str | None = None
    explanation_factors: list[ExplanationFactor] = Field(default_factory=list)
    scored_at: datetime | None = None
    updated_at: datetime | None = None
