import logging
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class MLRegistry:
    def __init__(self) -> None:
        self._models: dict[str, Any] = {}

    def load(self) -> None:
        path = Path(settings.ML_ARTIFACTS_DIR) / settings.ML_MODEL_FILE
        if not path.exists():
            logger.warning("ML artifact not found at %s - skipping load", path)
            return
        try:
            import joblib

            self._models["default"] = joblib.load(path)
            logger.info("Loaded ML model from %s", path)
        except Exception:
            logger.exception("Failed to load ML artifact at %s", path)

    def get(self, name: str = "default") -> Any:
        return self._models.get(name)


ml_registry = MLRegistry()
