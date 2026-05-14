from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FRENCH_MONTHS = {
    "janvier": 1,
    "fevrier": 2,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
    "décembre": 12,
}

CESSATION_DATE_RE = re.compile(
    r"date\s+de\s+cessation\s+des\s+paiements\s*(?::|le)?\s*"
    r"([0-9]{1,2})\s+([A-Za-z\u00c0-\u00ff]+)\s+([0-9]{4})",
    re.IGNORECASE,
)
MIN_REASONABLE_YEAR = 1900
MAX_FUTURE_YEARS = 1


@dataclass(frozen=True)
class BodaccParsedFile:
    parution: str | None
    date_parution: datetime | None
    annonces: list[dict[str, Any]]
    errors: list[str]


def parse_bodacc_xml_file(file_path: str | Path) -> BodaccParsedFile:
    path = Path(file_path)
    tree = ET.parse(path)
    return parse_bodacc_xml_root(tree.getroot())


def parse_bodacc_xml_content(content: bytes | str) -> BodaccParsedFile:
    return parse_bodacc_xml_root(ET.fromstring(content))


def parse_bodacc_xml_root(root: ET.Element) -> BodaccParsedFile:
    date_parution = _first_date(root, ("dateParution", "dateparution"))
    parution = _first_text(root, ("parution", "numeroParution", "nomPublication"))
    family = _detect_bodacc_family(root)
    annonces: list[dict[str, Any]] = []
    errors: list[str] = []

    for index, annonce in enumerate(_iter_announcement_nodes(root), start=1):
        try:
            parsed = _parse_annonce(annonce, date_parution, family)
            if _has_useful_annonce_fields(parsed):
                annonces.append(parsed)
        except Exception as exc:
            nojo = _first_text(annonce, ("nojo",))
            suffix = f" nojo={nojo}" if nojo else ""
            errors.append(f"annonce #{index}{suffix}: {exc}")

    return BodaccParsedFile(
        parution=parution,
        date_parution=date_parution,
        annonces=annonces,
        errors=errors,
    )


def _parse_annonce(
    element: ET.Element,
    date_parution: datetime | None,
    family: str,
) -> dict[str, Any]:
    personne_morale = _first_child(element, "personneMorale")
    personne_physique = _first_child(element, "personnePhysique")
    personne = personne_morale if personne_morale is not None else personne_physique
    personne_type = "morale" if personne_morale is not None else "physique" if personne_physique is not None else None
    identity = personne if personne is not None else element
    registration = _first_child(element, "numeroImmatriculation")
    jugement = _first_child(element, "jugement")

    jugement_nature = _first_text(jugement, ("nature", "jugementNature")) if jugement is not None else None
    jugement_text = _first_text(jugement, ("complementJugement", "texte", "complement")) if jugement is not None else None
    jugement_date = _first_date(jugement, ("date", "dateJugement", "jugementDate")) if jugement is not None else None
    risk_text = " ".join(part for part in (jugement_nature, jugement_text) if part)
    depot = _first_child(element, "depot")
    depot_date_cloture = _first_date(depot, ("dateCloture",)) if depot is not None else None
    depot_type = _first_text(depot, ("typeDepot",)) if depot is not None else None
    creation = _first_child(element, "creation")
    date_immatriculation = _first_date(creation, ("dateImmatriculation",)) if creation is not None else None
    date_commencement_activite = _first_date(creation, ("dateCommencementActivite",)) if creation is not None else None
    categorie_creation = _first_text(creation, ("categorieCreation",)) if creation is not None else None
    radiation = _first_child(element, "radiationAuRCS")
    modifications = _first_child(element, "modificationsGenerales")
    date_cessation_activite = _first_date(
        radiation,
        ("dateCessationActivitePP", "dateCessationActivitePM", "dateCessationActivite"),
    ) if radiation is not None else None
    radiation_text = _clean_text(" ".join(radiation.itertext())) if radiation is not None else None
    modification_text = _first_text(modifications, ("descriptif",)) if modifications is not None else None
    modification_date_commencement = _first_date(modifications, ("dateCommencementActivite",)) if modifications is not None else None
    is_radiation = radiation is not None

    personne_container = _first_child(element, "personne")
    adresse_node = _first_child(personne, "adresse") if personne is not None else None
    if adresse_node is None and personne_container is not None:
        adresse_node = _first_child(personne_container, "adresse")
    if adresse_node is None and personne_container is not None:
        adresse_node = _first_child(personne_container, "siegeSocial")
    if adresse_node is None:
        adresse_node = _first_child(element, "adresse")
    adresse_parts = _address_parts(adresse_node)

    siren = _normalize_siren(
        _first_text(identity, ("siren", "numeroIdentification", "numeroIdentificationRCS", "numeroImmatriculation"))
        or _first_text(registration, ("numeroIdentification", "numeroIdentificationRCS", "numeroImmatriculation"))
    )
    flags = extract_risk_flags(risk_text)
    now = datetime.now(timezone.utc)

    return {
        "nojo": _first_text(element, ("nojo",)),
        "numeroAnnonce": _first_text(element, ("numeroAnnonce", "numero")),
        "numeroDepartement": _first_text(element, ("numeroDepartement", "departement")),
        "tribunal": _first_text(element, ("tribunal",)),
        "identifiantClient": _first_text(element, ("identifiantClient",)),
        "personneType": personne_type,
        "siren": siren,
        "rcsCode": _first_text(identity, ("rcsCode", "codeRCS", "codeRcs")) or _first_text(registration, ("rcsCode", "codeRCS", "codeRcs")),
        "greffe": _first_text(identity, ("greffe", "nomGreffeImmat")) or _first_text(registration, ("greffe", "nomGreffeImmat")),
        "denomination": _first_text(identity, ("denomination", "denominationEIRL", "raisonSociale")),
        "nom": _first_text(identity, ("nom", "nomUsage")),
        "prenom": _first_text(identity, ("prenom", "prenoms")),
        "formeJuridique": _first_text(identity, ("formeJuridique",)),
        "enseigne": _first_text(identity, ("enseigne", "nomCommercial")) or _first_text(element, ("enseigne", "nomCommercial")),
        "activite": _first_text(identity, ("activite",)) or _first_text(element, ("activite",)),
        "adresse": adresse_parts["adresse"],
        "codePostal": adresse_parts["codePostal"],
        "ville": adresse_parts["ville"],
        "jugementFamille": _first_text(jugement, ("famille", "jugementFamille")) if jugement is not None else None,
        "jugementNature": jugement_nature,
        "jugementDate": jugement_date,
        "jugementText": jugement_text,
        "flags": flags,
        "dateCessationPaiement": extract_cessation_paiement_date(risk_text),
        "eventDate": jugement_date or date_cessation_activite or date_immatriculation or modification_date_commencement or date_parution,
        "bodaccFamily": family,
        "bodaccEdition": _bodacc_edition_for_family(family),
        "eventCategory": _event_category_for(family, jugement_nature, jugement_text, is_radiation),
        "eventType": _event_type_for(family, jugement_nature, jugement_text, depot_type, is_radiation),
        "rawTypeAnnonce": _first_type_annonce(element),
        "isRiskEvent": flags["procedureCollective"] or flags["cessationPaiement"] or flags["interdictionGerer"],
        "dateParution": date_parution,
        "dateClotureComptes": depot_date_cloture,
        "typeDepot": depot_type,
        "dateImmatriculation": date_immatriculation,
        "dateCommencementActivite": date_commencement_activite,
        "categorieCreation": categorie_creation,
        "dateCessationActivite": date_cessation_activite,
        "radiationText": radiation_text,
        "modificationText": modification_text,
        "isRadiation": is_radiation,
        "source": "BODACC",
        "createdAt": now,
        "updatedAt": now,
    }


def extract_risk_flags(text: str | None) -> dict[str, bool]:
    normalized = _normalize_text(text or "")
    liquidation = "liquidation judiciaire" in normalized
    redressement = "redressement judiciaire" in normalized
    sauvegarde = "sauvegarde" in normalized
    cessation = "cessation des paiements" in normalized
    interdiction = "interdiction de gerer" in normalized
    return {
        "liquidation": liquidation,
        "redressement": redressement,
        "sauvegarde": sauvegarde,
        "cessationPaiement": cessation,
        "interdictionGerer": interdiction,
        "procedureCollective": liquidation or redressement or sauvegarde,
    }


def extract_cessation_paiement_date(text: str | None) -> datetime | None:
    if not text:
        return None
    match = CESSATION_DATE_RE.search(text)
    if not match:
        return None
    day, month_name, year = match.groups()
    month = FRENCH_MONTHS.get(month_name.lower())
    if month is None:
        month = FRENCH_MONTHS.get(_strip_accents(month_name).lower())
    if month is None:
        return None
    return _keep_reasonable_date(datetime(int(year), month, int(day), tzinfo=timezone.utc))


def _has_useful_annonce_fields(annonce: dict[str, Any]) -> bool:
    useful_fields = (
        "nojo",
        "numeroAnnonce",
        "numeroDepartement",
        "tribunal",
        "identifiantClient",
        "personneType",
        "siren",
        "rcsCode",
        "greffe",
        "denomination",
        "nom",
        "prenom",
        "formeJuridique",
        "enseigne",
        "activite",
        "adresse",
        "codePostal",
        "ville",
        "jugementFamille",
        "jugementNature",
        "jugementDate",
        "jugementText",
        "dateCessationPaiement",
    )
    return any(annonce.get(field) is not None for field in useful_fields)


def _detect_bodacc_family(root: ET.Element) -> str:
    text = _local_name(root.tag).upper()
    if "PCL" in text:
        return "PCL"
    if "BILAN" in text:
        return "BILAN"
    if "RCS-A" in text or ("RCS" in text and ("_A" in text or "BXA" in text or "IMMAT" in text)):
        return "RCS_A"
    if "RCS-B" in text or ("RCS" in text and ("_B" in text or "BXB" in text)):
        return "RCS_B"
    return "UNKNOWN"


def _bodacc_edition_for_family(family: str) -> str | None:
    return {
        "PCL": "A",
        "RCS_A": "A",
        "RCS_B": "B",
        "BILAN": "C",
    }.get(family)


def _event_category_for(
    family: str,
    jugement_nature: str | None,
    jugement_text: str | None,
    is_radiation: bool = False,
) -> str:
    if family == "PCL":
        return "procedure_collective"
    if family == "BILAN":
        return "comptes_annuels"
    if family == "RCS_A":
        return "rcs_immatriculation"
    if family == "RCS_B":
        if is_radiation:
            return "radiation"
        return "rcs_modification"
    return "unknown"


def _event_type_for(
    family: str,
    jugement_nature: str | None,
    jugement_text: str | None,
    depot_type: str | None,
    is_radiation: bool = False,
) -> str | None:
    text = _normalize_text(" ".join(part for part in (jugement_nature, jugement_text, depot_type) if part))
    if "liquidation judiciaire" in text:
        return "liquidation_judiciaire"
    if "redressement judiciaire" in text:
        return "redressement_judiciaire"
    if "sauvegarde" in text:
        return "sauvegarde"
    if family == "RCS_A":
        if "achat" in text or "acquis" in text:
            return "achat_fonds"
        return "immatriculation"
    if family == "RCS_B":
        if is_radiation:
            return "radiation_rcs"
        return "modification_rcs"
    if family == "BILAN":
        return "depot_comptes"
    if jugement_nature:
        return _slugify(jugement_nature)
    if depot_type:
        return _slugify(depot_type)
    return None


def _first_type_annonce(element: ET.Element) -> str | None:
    type_annonce = _first_child(element, "typeAnnonce")
    if type_annonce is None:
        return None
    for child in list(type_annonce):
        return _local_name(child.tag)
    return _clean_text(" ".join(type_annonce.itertext())) or None


def _slugify(value: str) -> str:
    normalized = _normalize_text(value)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _address_parts(element: ET.Element | None) -> dict[str, str | None]:
    if element is None:
        return {"adresse": None, "codePostal": None, "ville": None}
    code_postal = _first_text(element, ("codePostal", "code_postal"))
    ville = _first_text(element, ("ville", "commune"))
    exclude = {"codePostal", "code_postal", "ville", "commune"}
    lines = [
        _clean_text(child_text)
        for child in element.iter()
        if _local_name(child.tag) not in exclude
        if len(list(child)) == 0
        for child_text in [child.text]
        if child_text and child_text.strip()
    ]
    adresse = " ".join(dict.fromkeys(lines)) or _clean_text(" ".join(element.itertext()))
    return {"adresse": adresse or None, "codePostal": code_postal, "ville": ville}


def _normalize_siren(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits if len(digits) == 9 else None


def _first_child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    wanted = name.lower()
    return next((child for child in element.iter() if _local_name(child.tag).lower() == wanted), None)


def _iter_announcement_nodes(root: ET.Element) -> Iterable[ET.Element]:
    avis_nodes = list(_iter_by_name(root, "avis"))
    if avis_nodes:
        yield from avis_nodes
        return

    for annonce in _iter_by_name(root, "annonce"):
        if list(annonce) or _clean_text(" ".join(annonce.itertext())):
            yield annonce


def _iter_by_name(element: ET.Element, name: str) -> Iterable[ET.Element]:
    wanted = name.lower()
    for child in element.iter():
        if _local_name(child.tag).lower() == wanted:
            yield child


def _first_text(element: ET.Element | None, names: tuple[str, ...]) -> str | None:
    if element is None:
        return None
    wanted = {name.lower() for name in names}
    for child in element.iter():
        if _local_name(child.tag).lower() in wanted:
            text = _clean_text(" ".join(child.itertext()))
            if text:
                return text
    return None


def _first_date(element: ET.Element | None, names: tuple[str, ...]) -> datetime | None:
    value = _first_text(element, names)
    return _parse_date(value)


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y%m%d"):
        try:
            return _keep_reasonable_date(datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc))
        except ValueError:
            pass
    match = re.search(r"([0-9]{1,2})\s+([A-Za-z\u00c0-\u00ff]+)\s+([0-9]{4})", cleaned)
    if match:
        day, month_name, year = match.groups()
        month = FRENCH_MONTHS.get(month_name.lower()) or FRENCH_MONTHS.get(_strip_accents(month_name).lower())
        if month is not None:
            return _keep_reasonable_date(datetime(int(year), month, int(day), tzinfo=timezone.utc))
    return None


def _keep_reasonable_date(value: datetime) -> datetime | None:
    max_year = datetime.now(timezone.utc).year + MAX_FUTURE_YEARS
    if MIN_REASONABLE_YEAR <= value.year <= max_year:
        return value
    return None


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", _repair_mojibake(value)).strip()


def _repair_mojibake(value: str) -> str:
    if not value or not any(marker in value for marker in ("Ã", "Â", "â")):
        return value
    try:
        repaired = value.encode("cp1252").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired else value


def _normalize_text(value: str) -> str:
    return _strip_accents(value).lower()


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
