"""Export BODACC TAZ/TAR archives to chunked Parquet event rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.config import settings
from app.services.bodacc_xml_parser import parse_bodacc_xml_content

logger = logging.getLogger("bodacc_to_parquet")


def main() -> None:
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    year = args.year or _infer_year(input_path.name)
    mode = args.mode
    output_base = Path(args.output_dir or settings.DATA_LAKE_DIR) / "raw" / "bodacc"
    output_dir = output_base / mode / str(year or "unknown") / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(
        "export start input=%s output=%s mode=%s year=%s batch_size=%d include_raw_json=%s",
        input_path,
        output_dir,
        mode,
        year,
        args.batch_size,
        args.include_raw_json,
    )
    started_at = datetime.now(tz=timezone.utc)
    rows = export_bodacc_archive_to_parquet(
        input_path=input_path,
        output_dir=output_dir,
        mode=mode,
        year=year,
        source_url=args.source_url,
        batch_size=args.batch_size,
        max_records=args.max_records,
        include_raw_json=args.include_raw_json,
    )
    elapsed = datetime.now(tz=timezone.utc) - started_at
    logger.info("export done rows=%d elapsed=%s output=%s", rows, elapsed, output_dir)


def export_bodacc_archive_to_parquet(
    *,
    input_path: Path,
    output_dir: Path,
    mode: str,
    year: int | None,
    source_url: str | None = None,
    batch_size: int = 100_000,
    max_records: int | None = None,
    include_raw_json: bool = False,
) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    part = 0
    batch: list[dict[str, Any]] = []
    members = 0
    parse_errors = 0
    archive_name = input_path.name
    source = source_url or str(input_path)

    with tarfile.open(input_path, mode="r:*") as tf:
        for member in tf:
            if not member.isfile():
                continue
            members += 1
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            content = extracted.read()
            member_key = hashlib.sha256(
                source.encode("utf-8") + b"\0" + member.name.encode("utf-8") + b"\0" + content
            ).hexdigest()
            try:
                parsed = parse_bodacc_xml_content(content)
            except Exception as exc:
                parse_errors += 1
                logger.warning("parse failed member=%s error=%s", member.name, exc)
                continue

            for index, annonce in enumerate(parsed.annonces, start=1):
                row = _row_from_annonce(
                    annonce,
                    archive_name=archive_name,
                    member_name=member.name,
                    member_key=member_key,
                    annonce_index=index,
                    mode=mode,
                    year=year,
                    source_url=source_url,
                    include_raw_json=include_raw_json,
                )
                batch.append(row)
                if len(batch) >= batch_size:
                    part += 1
                    _write_batch(batch, output_dir, part)
                    total += len(batch)
                    logger.info("wrote part=%05d batch_rows=%d total_rows=%d", part, len(batch), total)
                    _write_progress(output_dir, input_path, mode, year, total, part, members, parse_errors, done=False)
                    batch.clear()

                if max_records is not None and total + len(batch) >= max_records:
                    break
            if max_records is not None and total + len(batch) >= max_records:
                break

    if batch:
        part += 1
        _write_batch(batch, output_dir, part)
        total += len(batch)
        logger.info("wrote part=%05d batch_rows=%d total_rows=%d", part, len(batch), total)
        _write_progress(output_dir, input_path, mode, year, total, part, members, parse_errors, done=False)

    manifest = {
        "input_path": str(input_path),
        "mode": mode,
        "year": year,
        "rows": total,
        "parts": part,
        "members": members,
        "parse_errors": parse_errors,
        "include_raw_json": include_raw_json,
        "exported_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    (output_dir / "_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_progress(output_dir, input_path, mode, year, total, part, members, parse_errors, done=True)
    return total


def _row_from_annonce(
    annonce: dict[str, Any],
    *,
    archive_name: str,
    member_name: str,
    member_key: str,
    annonce_index: int,
    mode: str,
    year: int | None,
    source_url: str | None,
    include_raw_json: bool,
) -> dict[str, Any]:
    record_key = annonce.get("nojo") or f"{member_key}:{annonce_index}"
    flags = annonce.get("flags") if isinstance(annonce.get("flags"), dict) else {}
    row: dict[str, Any] = {
        "record_key": str(record_key),
        "nojo": _as_str(annonce.get("nojo")),
        "siren": _as_str(annonce.get("siren")),
        "denomination": _as_str(annonce.get("denomination")),
        "nom": _as_str(annonce.get("nom")),
        "prenom": _as_str(annonce.get("prenom")),
        "personne_type": _as_str(annonce.get("personneType")),
        "bodacc_family": _as_str(annonce.get("bodaccFamily")),
        "bodacc_edition": _as_str(annonce.get("bodaccEdition")),
        "event_category": _as_str(annonce.get("eventCategory")),
        "event_type": _as_str(annonce.get("eventType")),
        "event_date": _dt(annonce.get("eventDate")),
        "date_parution": _dt(annonce.get("dateParution")),
        "jugement_date": _dt(annonce.get("jugementDate")),
        "date_cessation_paiement": _dt(annonce.get("dateCessationPaiement")),
        "date_cloture_comptes": _dt(annonce.get("dateClotureComptes")),
        "numero_annonce": _as_str(annonce.get("numeroAnnonce")),
        "numero_departement": _as_str(annonce.get("numeroDepartement")),
        "tribunal": _as_str(annonce.get("tribunal")),
        "greffe": _as_str(annonce.get("greffe")),
        "forme_juridique": _as_str(annonce.get("formeJuridique")),
        "activite": _as_str(annonce.get("activite")),
        "adresse": _as_str(annonce.get("adresse")),
        "code_postal": _as_str(annonce.get("codePostal")),
        "ville": _as_str(annonce.get("ville")),
        "jugement_nature": _as_str(annonce.get("jugementNature")),
        "jugement_text": _as_str(annonce.get("jugementText")),
        "is_risk_event": _as_bool(annonce.get("isRiskEvent")),
        "is_radiation": _as_bool(annonce.get("isRadiation")),
        "flag_liquidation": _as_bool(flags.get("liquidation")),
        "flag_redressement": _as_bool(flags.get("redressement")),
        "flag_sauvegarde": _as_bool(flags.get("sauvegarde")),
        "flag_cessation_paiement": _as_bool(flags.get("cessationPaiement")),
        "flag_interdiction_gerer": _as_bool(flags.get("interdictionGerer")),
        "flag_procedure_collective": _as_bool(flags.get("procedureCollective")),
        "archive_name": archive_name,
        "archive_member_name": member_name,
        "source_url": source_url,
        "mode": mode,
        "year": year,
        "exported_at": datetime.now(tz=timezone.utc),
    }
    if include_raw_json:
        row["raw_json"] = json.dumps(annonce, ensure_ascii=False, separators=(",", ":"), default=str)
    return row


def _write_batch(rows: list[dict[str, Any]], output_dir: Path, part: int) -> None:
    table = pa.Table.from_pylist(rows, schema=_schema("raw_json" in rows[0]))
    target = output_dir / f"part-{part:05d}.parquet"
    tmp = target.with_suffix(".parquet.tmp")
    pq.write_table(
        table,
        tmp,
        compression="zstd",
        compression_level=6,
        use_dictionary=True,
        write_statistics=True,
    )
    tmp.replace(target)


def _write_progress(
    output_dir: Path,
    input_path: Path,
    mode: str,
    year: int | None,
    rows: int,
    parts: int,
    members: int,
    parse_errors: int,
    *,
    done: bool,
) -> None:
    progress = {
        "input_path": str(input_path),
        "mode": mode,
        "year": year,
        "rows": rows,
        "parts": parts,
        "members": members,
        "parse_errors": parse_errors,
        "done": done,
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    tmp = output_dir / "_progress.json.tmp"
    tmp.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(output_dir / "_progress.json")


def _schema(include_raw_json: bool) -> pa.Schema:
    fields = [
        pa.field("record_key", pa.string()),
        pa.field("nojo", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("denomination", pa.string()),
        pa.field("nom", pa.string()),
        pa.field("prenom", pa.string()),
        pa.field("personne_type", pa.string()),
        pa.field("bodacc_family", pa.string()),
        pa.field("bodacc_edition", pa.string()),
        pa.field("event_category", pa.string()),
        pa.field("event_type", pa.string()),
        pa.field("event_date", pa.timestamp("us", tz="UTC")),
        pa.field("date_parution", pa.timestamp("us", tz="UTC")),
        pa.field("jugement_date", pa.timestamp("us", tz="UTC")),
        pa.field("date_cessation_paiement", pa.timestamp("us", tz="UTC")),
        pa.field("date_cloture_comptes", pa.timestamp("us", tz="UTC")),
        pa.field("numero_annonce", pa.string()),
        pa.field("numero_departement", pa.string()),
        pa.field("tribunal", pa.string()),
        pa.field("greffe", pa.string()),
        pa.field("forme_juridique", pa.string()),
        pa.field("activite", pa.string()),
        pa.field("adresse", pa.string()),
        pa.field("code_postal", pa.string()),
        pa.field("ville", pa.string()),
        pa.field("jugement_nature", pa.string()),
        pa.field("jugement_text", pa.string()),
        pa.field("is_risk_event", pa.bool_()),
        pa.field("is_radiation", pa.bool_()),
        pa.field("flag_liquidation", pa.bool_()),
        pa.field("flag_redressement", pa.bool_()),
        pa.field("flag_sauvegarde", pa.bool_()),
        pa.field("flag_cessation_paiement", pa.bool_()),
        pa.field("flag_interdiction_gerer", pa.bool_()),
        pa.field("flag_procedure_collective", pa.bool_()),
        pa.field("archive_name", pa.string()),
        pa.field("archive_member_name", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("mode", pa.string()),
        pa.field("year", pa.int32()),
        pa.field("exported_at", pa.timestamp("us", tz="UTC")),
    ]
    if include_raw_json:
        fields.append(pa.field("raw_json", pa.string()))
    return pa.schema(fields)


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


def _infer_year(name: str) -> int | None:
    digits = "".join(ch if ch.isdigit() else " " for ch in name).split()
    for token in digits:
        if len(token) >= 4:
            year = int(token[:4])
            if 1900 <= year <= 2100:
                return year
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export BODACC TAZ/TAR archives to Parquet.")
    parser.add_argument("--input", required=True, help="Path to a BODACC .taz/.tar/.tar.gz archive.")
    parser.add_argument(
        "--output-dir",
        help=(
            "Base data-lake directory. Defaults to DATA_LAKE_DIR and writes under "
            "<DATA_LAKE_DIR>/raw/bodacc/..."
        ),
    )
    parser.add_argument("--mode", choices=("current", "historical"), default="current")
    parser.add_argument("--year", type=int)
    parser.add_argument("--source-url")
    parser.add_argument("--batch-size", type=int, default=100_000)
    parser.add_argument("--max-records", type=int)
    parser.add_argument(
        "--include-raw-json",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Store parsed announcement JSON in Parquet. Disabled by default.",
    )
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


if __name__ == "__main__":
    main()
