"""Feature registry: a queryable index over `config/feature_registry.yaml`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from .config import DEFAULT_FEATURE_REGISTRY_PATH


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    sources: tuple[str, ...]
    description: str
    type: str                       # "numeric" | "categorical"
    supervised_allowed: bool
    leakage_risk: str               # "low" | "medium" | "high"
    known_at_inference: bool
    physique_only: bool = False
    anomaly: bool = False


class FeatureRegistry:
    """In-memory, queryable feature registry."""

    def __init__(self, specs: list[FeatureSpec]):
        self._specs: dict[str, FeatureSpec] = {s.name: s for s in specs}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "FeatureRegistry":
        p = Path(path) if path else DEFAULT_FEATURE_REGISTRY_PATH
        with p.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        specs = [cls._parse(entry) for entry in raw["features"]]
        return cls(specs)

    @staticmethod
    def _parse(entry: dict) -> FeatureSpec:
        return FeatureSpec(
            name=entry["name"],
            sources=tuple(entry.get("sources", [])),
            description=entry["description"],
            type=entry["type"],
            supervised_allowed=bool(entry["supervised_allowed"]),
            leakage_risk=entry["leakage_risk"],
            known_at_inference=bool(entry["known_at_inference"]),
            physique_only=bool(entry.get("physique_only", False)),
            anomaly=bool(entry.get("anomaly", False)),
        )

    # ---- queries ----------------------------------------------------------

    def all(self) -> list[FeatureSpec]:
        return list(self._specs.values())

    def get(self, name: str) -> FeatureSpec:
        return self._specs[name]

    def supervised_features(self) -> list[FeatureSpec]:
        return [s for s in self._specs.values() if s.supervised_allowed]

    def supervised_numeric(self, available: Iterable[str] | None = None) -> list[str]:
        return self._filter_names(
            lambda s: s.supervised_allowed and s.type == "numeric",
            available,
        )

    def supervised_categorical(self, available: Iterable[str] | None = None) -> list[str]:
        return self._filter_names(
            lambda s: s.supervised_allowed and s.type == "categorical",
            available,
        )

    def physique_features(self, available: Iterable[str] | None = None) -> list[str]:
        return self._filter_names(
            lambda s: s.physique_only or s.supervised_allowed,
            available,
        )

    def anomaly_features(self, available: Iterable[str] | None = None) -> list[str]:
        return self._filter_names(lambda s: s.anomaly, available)

    def excluded_leakage(self) -> list[FeatureSpec]:
        return [s for s in self._specs.values() if s.leakage_risk == "high"]

    # ---- helpers ----------------------------------------------------------

    def _filter_names(
        self, predicate, available: Iterable[str] | None
    ) -> list[str]:
        names = [s.name for s in self._specs.values() if predicate(s)]
        if available is None:
            return names
        avail = set(available)
        return [n for n in names if n in avail]

    def schema(self) -> list[dict]:
        """Export the registry as a JSON-friendly list (for metadata dumps)."""

        return [
            {
                "name": s.name,
                "sources": list(s.sources),
                "description": s.description,
                "type": s.type,
                "supervised_allowed": s.supervised_allowed,
                "leakage_risk": s.leakage_risk,
                "known_at_inference": s.known_at_inference,
                "physique_only": s.physique_only,
                "anomaly": s.anomaly,
            }
            for s in self._specs.values()
        ]
