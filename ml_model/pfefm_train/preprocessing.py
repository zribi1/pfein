"""Preprocessing pipeline factory.

The returned object is an ``sklearn.compose.ColumnTransformer`` that:

* keeps numeric columns as-is (boosters handle NaN natively; for linear/tree
  baselines we impute with the median in-pipe).
* encodes categoricals with ``OrdinalEncoder`` and ``handle_unknown="use_encoded_value"``
  mapping unseen categories to -1. This avoids the brittle ``LabelEncoder``
  "Inconnu" hack used in the legacy notebook and works correctly at inference
  time on cold categories.

The transformer preserves feature order so downstream tools (SHAP, importance)
can map indices back to names.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

CategoricalStrategy = Literal["ordinal"]
NumericStrategy = Literal["passthrough", "median_impute"]


def _categorical_pipeline() -> Pipeline:
    """Cast-to-string -> OrdinalEncoder with unknown_value=-1."""

    return Pipeline(
        steps=[
            ("to_str", _StringCaster()),
            (
                "ordinal",
                OrdinalEncoder(
                    handle_unknown="use_encoded_value",
                    unknown_value=-1,
                    encoded_missing_value=-1,
                    dtype=np.float64,
                ),
            ),
        ]
    )


def _numeric_pipeline(strategy: NumericStrategy) -> Pipeline:
    if strategy == "passthrough":
        return Pipeline(steps=[("identity", _NumericCaster())])
    if strategy == "median_impute":
        return Pipeline(
            steps=[
                ("to_num", _NumericCaster()),
                ("impute", SimpleImputer(strategy="median")),
            ]
        )
    raise ValueError(f"Unknown numeric strategy: {strategy!r}")


def make_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
    *,
    numeric_strategy: NumericStrategy = "passthrough",
) -> ColumnTransformer:
    """Build a :class:`ColumnTransformer` preserving feature order."""

    transformers = []
    if numeric_features:
        transformers.append(
            ("num", _numeric_pipeline(numeric_strategy), numeric_features)
        )
    if categorical_features:
        transformers.append(("cat", _categorical_pipeline(), categorical_features))

    return ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        verbose_feature_names_out=False,
    )


def feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Return the output feature names in positional order."""

    return list(preprocessor.get_feature_names_out())


# ---- small stateless helpers (picklable) ---------------------------------


class _StringCaster:
    """Cast every column to `str` (keeping NaN as "nan" for the ordinal encoder)."""

    def fit(self, X, y=None):  # noqa: D401
        return self

    def transform(self, X):
        df = pd.DataFrame(X).copy()
        for c in df.columns:
            df[c] = df[c].where(df[c].notna(), other=np.nan).astype(object)
            df[c] = df[c].map(lambda v: "__nan__" if pd.isna(v) else str(v))
        return df

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features, dtype=object)


class _NumericCaster:
    """Cast every column to numeric (NaN on failure)."""

    def fit(self, X, y=None):  # noqa: D401
        return self

    def transform(self, X):
        df = pd.DataFrame(X).copy()
        for c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.to_numpy(dtype=np.float64)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features, dtype=object)
