"""Typed configuration loader backed by `config/config.yaml`."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "config.yaml"
DEFAULT_FEATURE_REGISTRY_PATH = CONFIG_DIR / "feature_registry.yaml"
DEFAULT_PHYSIQUE_RULES_PATH = CONFIG_DIR / "physique_rules.yaml"


@dataclass(frozen=True)
class Paths:
    input_parquet: Path
    artifacts_root: Path
    backend_artifacts_dir: Path
    backend_model_filename: str


@dataclass(frozen=True)
class SplitConfig:
    test_cutoff: date
    rolling_folds: int
    fold_gap_years: int


@dataclass(frozen=True)
class ThresholdConfig:
    strategy: str
    min_precision: float
    cost_false_negative: float
    cost_false_positive: float


@dataclass(frozen=True)
class RiskBand:
    label: str
    min_prob: float


@dataclass(frozen=True)
class AnomalyConfig:
    contamination: float
    n_estimators: int


@dataclass(frozen=True)
class PipelineConfig:
    paths: Paths
    reference_date: date
    split: SplitConfig
    target_column: str
    target_event_value: int
    hyperparameters: dict[str, dict[str, Any]]
    candidates: list[str]
    selection_metric: str
    threshold: ThresholdConfig
    risk_bands_morale: list[RiskBand]
    calibration_method: str
    anomaly: AnomalyConfig
    top_k_grid: list[int]
    random_state: int
    verbose: bool
    raw: dict[str, Any] = field(repr=False)


def _resolve_path(base: Path, p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (base / path).resolve()


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value == "today":
        return date.today()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def load_config(path: str | Path | None = None) -> PipelineConfig:
    """Load the training configuration from YAML and validate its shape."""

    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    base = cfg_path.parent.parent  # ml_model/
    paths_raw = raw["paths"]
    paths = Paths(
        input_parquet=_resolve_path(base, paths_raw["input_parquet"]),
        artifacts_root=_resolve_path(base, paths_raw["artifacts_root"]),
        backend_artifacts_dir=_resolve_path(base, paths_raw["backend_artifacts_dir"]),
        backend_model_filename=paths_raw["backend_model_filename"],
    )

    split_raw = raw["split"]
    split = SplitConfig(
        test_cutoff=_parse_date(split_raw["test_cutoff"]),
        rolling_folds=int(split_raw["rolling_folds"]),
        fold_gap_years=int(split_raw["fold_gap_years"]),
    )

    thr_raw = raw["threshold"]
    threshold = ThresholdConfig(
        strategy=thr_raw["strategy"],
        min_precision=float(thr_raw["min_precision"]),
        cost_false_negative=float(thr_raw["cost_false_negative"]),
        cost_false_positive=float(thr_raw["cost_false_positive"]),
    )

    bands = [
        RiskBand(label=b["label"], min_prob=float(b["min"]))
        for b in raw["risk_bands_morale"]
    ]

    anomaly = AnomalyConfig(
        contamination=float(raw["anomaly"]["contamination"]),
        n_estimators=int(raw["anomaly"]["n_estimators"]),
    )

    return PipelineConfig(
        paths=paths,
        reference_date=_parse_date(raw["reference_date"]),
        split=split,
        target_column=raw["target"]["source_column"],
        target_event_value=int(raw["target"]["event_value"]),
        hyperparameters=raw["hyperparameters"],
        candidates=list(raw["candidates"]),
        selection_metric=raw["selection_metric"],
        threshold=threshold,
        risk_bands_morale=bands,
        calibration_method=raw.get("calibration", {}).get("method", "none"),
        anomaly=anomaly,
        top_k_grid=list(raw["top_k_grid"]),
        random_state=int(raw["random_state"]),
        verbose=bool(raw.get("verbose", True)),
        raw=raw,
    )
