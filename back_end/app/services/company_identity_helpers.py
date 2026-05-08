from __future__ import annotations

from typing import Any


def extract_siren(source: str, payload: dict[str, Any]) -> str | None:
    siren, _ = extract_siren_with_detail(source, payload)
    return siren


def extract_siren_with_detail(source: str, payload: dict[str, Any]) -> tuple[str | None, str]:
    paths: list[tuple[str, ...]]
    if source == "insee":
        paths = [
            ("siren",),
            ("periodesUniteLegale", "0", "siren"),
            ("uniteLegale", "siren"),
        ]
    elif source == "inpi":
        paths = [
            ("siren",),
            ("company", "siren"),
            ("entreprise", "siren"),
            ("formality", "content", "personneMorale", "identite", "entreprise", "siren"),
            ("formality", "content", "personnePhysique", "identite", "entreprise", "siren"),
        ]
    else:
        paths = [
            ("siren",),
            ("record", "siren"),
            ("fields", "siren"),
            ("personne", "numeroImmatriculation", "numeroIdentification", "numeroSiren"),
        ]

    checked_details: list[str] = []
    best_attempt: str | None = None
    for path in paths:
        raw = get_nested_value(payload, path)
        normalized = normalize_siren(raw)
        if normalized:
            return normalized, ""
        path_str = ".".join(path)
        if raw is not None:
            best_attempt = str(raw)
            digits = "".join(ch for ch in str(raw) if ch.isdigit())
            checked_details.append(f"{path_str}={raw!r} ({len(digits)} digits, expected 9)")
        else:
            checked_details.append(f"{path_str}=<missing>")

    if best_attempt:
        detail = f"invalid siren; checked: {'; '.join(checked_details)}"
    else:
        detail = f"no siren found; checked paths: {'; '.join(checked_details)}"
    return None, detail


def extract_denomination(source: str, payload: dict[str, Any]) -> str | None:
    if source == "insee":
        paths = (
            ("denominationUniteLegale",),
            ("periodesUniteLegale", "0", "denominationUniteLegale"),
            ("periodesUniteLegale", "0", "nomUniteLegale"),
        )
    elif source == "inpi":
        paths = (
            ("denomination",),
            ("company", "name"),
            ("entreprise", "denomination"),
            ("formality", "content", "personneMorale", "identite", "entreprise", "denomination"),
            ("formality", "content", "personnePhysique", "identite", "entreprise", "nomCommercial"),
        )
    else:
        paths = (
            ("denomination",),
            ("fields", "denomination"),
            ("fields", "nom_commercial"),
            ("record", "fields", "denomination"),
        )

    for path in paths:
        value = get_nested_value(payload, path)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_list(payload: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value

    list_keys = [key for key, value in payload.items() if isinstance(value, list)]
    if len(list_keys) == 1:
        return payload[list_keys[0]]
    return []


def get_nested_value(payload: Any, path: tuple[str, ...]) -> Any:
    current = payload
    for key in path:
        if isinstance(current, list):
            if not key.isdigit():
                return None
            index = int(key)
            if index >= len(current):
                return None
            current = current[index]
            continue
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def normalize_siren(value: Any) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) != 9:
        return None
    return digits
