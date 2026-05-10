from __future__ import annotations

import argparse
import ftplib
import os
import shutil
import socket
import stat
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Iterator

from common import (
    DEFAULT_DRIVE_ROOT,
    install_deps,
    seed_file_from_drive,
    storage_paths,
    sync_file_to_drive,
    write_json,
)


VALID_CATEGORIES = {"comptes_annuels", "formalites"}
VALID_NIVEAUX = {"standard", "niveau1"}


@dataclass(frozen=True)
class RemoteArchive:
    path: str
    size: int
    mtime: datetime | None
    category: str
    niveau: str


class InpiConnector:
    def __init__(self, args: argparse.Namespace) -> None:
        self.protocol = args.protocol.lower()
        self.host = args.host or os.getenv("INPI_FTP_HOST", "")
        self.port = int(args.port or os.getenv("INPI_FTP_PORT") or (22 if self.protocol == "sftp" else 21))
        self.user = args.user or os.getenv("INPI_FTP_USER", "")
        self.password = args.password or os.getenv("INPI_FTP_PASSWORD", "")
        self.timeout = int(args.timeout)
        self.ftp: ftplib.FTP | None = None
        self.sftp = None
        self.transport = None
        if not self.host or not self.user or not self.password:
            raise RuntimeError("INPI credentials missing. Set INPI_FTP_HOST, INPI_FTP_USER, and INPI_FTP_PASSWORD.")

    def __enter__(self) -> "InpiConnector":
        if self.protocol == "sftp":
            import paramiko

            self.transport = paramiko.Transport((self.host, self.port))
            self.transport.banner_timeout = self.timeout
            self.transport.connect(username=self.user, password=self.password)
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
            self.sftp.get_channel().settimeout(self.timeout)
        else:
            self.ftp = ftplib.FTP(timeout=self.timeout)
            self.ftp.connect(self.host, self.port, timeout=self.timeout)
            self.ftp.login(self.user, self.password)
            self.ftp.set_pasv(True)
        print(f"[inpi] connected protocol={self.protocol} host={self.host} port={self.port}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        try:
            if self.sftp is not None:
                self.sftp.close()
        finally:
            if self.transport is not None:
                self.transport.close()
            if self.ftp is not None:
                try:
                    self.ftp.quit()
                except Exception:
                    self.ftp.close()
        self.sftp = None
        self.transport = None
        self.ftp = None

    def reconnect(self) -> None:
        self.close()
        self.__enter__()

    def walk(self, base: str) -> Iterator[tuple[str, int, datetime | None]]:
        if self.protocol == "sftp":
            yield from self._walk_sftp(base)
        else:
            yield from self._walk_ftp(base)

    def _walk_sftp(self, base: str) -> Iterator[tuple[str, int, datetime | None]]:
        stack = [base or "/"]
        while stack:
            current = stack.pop()
            for entry in self.sftp.listdir_attr(current):
                if entry.filename in (".", ".."):
                    continue
                child = _join_posix(current, entry.filename)
                if stat.S_ISDIR(entry.st_mode or 0):
                    stack.append(child)
                    continue
                mtime = datetime.fromtimestamp(entry.st_mtime, tz=timezone.utc) if entry.st_mtime else None
                yield child, int(entry.st_size or 0), mtime

    def _walk_ftp(self, base: str) -> Iterator[tuple[str, int, datetime | None]]:
        assert self.ftp is not None
        stack = [base or "/"]
        seen = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            try:
                entries = list(self.ftp.mlsd(current))
                use_mlsd = True
            except Exception:
                entries = [(name, {}) for name in self.ftp.nlst(current)]
                use_mlsd = False
            for name, facts in entries:
                if name in (".", ".."):
                    continue
                child = name if name.startswith("/") else _join_posix(current, name)
                if _ftp_is_dir(self.ftp, child, facts, use_mlsd):
                    stack.append(child)
                    continue
                size = int(facts.get("size") or 0) if use_mlsd else _ftp_size(self.ftp, child)
                mtime = _parse_mlsd_modify(facts.get("modify")) if use_mlsd else _ftp_mdtm(self.ftp, child)
                yield child, size, mtime

    def download(self, remote_path: str, local_path: Path, *, size: int, overwrite: bool) -> None:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        if local_path.exists() and not overwrite and (not size or local_path.stat().st_size == size):
            print(f"[inpi] skip existing {local_path}")
            return
        tmp = local_path.with_suffix(local_path.suffix + ".part")
        if overwrite and tmp.exists():
            tmp.unlink()
        if not overwrite and local_path.exists() and (not tmp.exists() or local_path.stat().st_size > tmp.stat().st_size):
            local_size = local_path.stat().st_size
            if size and local_size < size:
                print(
                    f"[inpi] found incomplete final file; moving to resume partial "
                    f"{local_path.name} ({local_size / 1024 / 1024:,.1f} MB)"
                )
                if tmp.exists():
                    tmp.unlink()
                local_path.replace(tmp)
        written = tmp.stat().st_size if tmp.exists() else 0
        if written:
            if size and written > size:
                print(f"[inpi] partial file is larger than expected; restarting {local_path.name}")
                tmp.unlink()
                written = 0
            elif size and written == size:
                tmp.replace(local_path)
                print(f"[inpi] completed from existing partial {local_path}")
                return
            else:
                print(f"[inpi] resume {local_path.name} from {written / 1024 / 1024:,.1f} MB")
        started = time.monotonic()
        with tmp.open("ab" if written else "wb") as handle:
            def write_chunk(chunk: bytes) -> None:
                nonlocal written
                handle.write(chunk)
                written += len(chunk)
                if written and written % (100 * 1024 * 1024) < len(chunk):
                    _print_progress(local_path.name, written, size, started)

            if self.protocol == "sftp":
                with self.sftp.open(remote_path, "rb") as remote:
                    if written:
                        remote.seek(written)
                    remote.prefetch()
                    while True:
                        chunk = remote.read(1024 * 1024)
                        if not chunk:
                            break
                        write_chunk(chunk)
            else:
                assert self.ftp is not None
                try:
                    self.ftp.voidcmd("TYPE I")
                    self.ftp.retrbinary(
                        f"RETR {remote_path}",
                        write_chunk,
                        blocksize=1024 * 1024,
                        rest=written or None,
                    )
                except TimeoutError:
                    if size and written >= size:
                        print(f"[inpi] control connection timed out after complete transfer: {local_path.name}")
                    else:
                        print(
                            f"[inpi] transfer timed out before completion: {local_path.name} "
                            f"written={written:,} expected={size:,}; rerun to resume"
                        )
                        raise
                except socket.timeout:
                    if size and written >= size:
                        print(f"[inpi] control connection timed out after complete transfer: {local_path.name}")
                    else:
                        print(
                            f"[inpi] transfer timed out before completion: {local_path.name} "
                            f"written={written:,} expected={size:,}; rerun to resume"
                        )
                        raise
                except OSError as exc:
                    if size and written >= size:
                        print(f"[inpi] control connection failed after complete transfer: {local_path.name} ({exc})")
                    else:
                        print(
                            f"[inpi] transfer failed before completion: {local_path.name} "
                            f"written={written:,} expected={size:,}; rerun to resume ({exc})"
                        )
                        raise
        if size and written != size:
            raise RuntimeError(f"size mismatch for {remote_path}: wrote {written}, expected {size}")
        tmp.replace(local_path)
        _print_progress(local_path.name, written, size, started)


def main() -> None:
    args = parse_args()
    repo_dir = Path(args.repo_dir).resolve()
    if args.install_deps:
        install_deps(repo_dir)
    drive_p, work_p = storage_paths(args.drive_root, args.work_dir)
    p = work_p
    categories = _split_filter(args.categories)
    niveaux = _split_filter(args.niveaux)
    with InpiConnector(args) as conn:
        print(
            "[inpi] discovery phase start "
            f"base={args.remote_base_dir or '/'} categories={','.join(sorted(categories)) or '*'} "
            f"niveaux={','.join(sorted(niveaux)) or '*'}"
        )
        archives = discover(conn, args.remote_base_dir, categories=categories, niveaux=niveaux)
        print(f"[inpi] discovered {len(archives)} matching archive(s)")
        selected = archives[: args.max_files or len(archives)]
        print(f"[inpi] download phase start selected={len(selected)}")
        for index, archive in enumerate(selected, start=1):
            local_path = local_path_for(p["source_archives"] / "inpi", archive.path)
            print(f"[inpi] download {index}/{len(selected)} {archive.path}")
            if args.work_dir and seed_file_from_drive(local_path, p["drive_root"], drive_p["drive_root"]):
                print(f"[inpi] seeded local work file from Drive: {local_path.name}")
            if args.work_dir and seed_partial_from_drive(local_path, p["drive_root"], drive_p["drive_root"]):
                print(f"[inpi] seeded local partial from Drive: {local_path.name}.part")
            download_ok = download_with_retries(
                conn,
                archive.path,
                local_path,
                size=archive.size,
                overwrite=args.overwrite,
                retries=args.retries,
                drive_root=drive_p["drive_root"] if args.work_dir else None,
                local_root=p["drive_root"] if args.work_dir else None,
            )
            if not download_ok:
                continue
            manifest_path = local_path.with_suffix(local_path.suffix + ".manifest.json")
            write_json(
                manifest_path,
                {
                    "source": "inpi_ftp_colab_download",
                    "remote_path": archive.path,
                    "remote_size": archive.size,
                    "remote_mtime": archive.mtime.isoformat() if archive.mtime else None,
                    "local_path": str(local_path),
                    "local_size": local_path.stat().st_size,
                    "category": archive.category,
                    "niveau": archive.niveau,
                    "downloaded_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            if args.work_dir:
                sync_file_to_drive(local_path, p["drive_root"], drive_p["drive_root"])
                remove_drive_partial(local_path, p["drive_root"], drive_p["drive_root"])
                sync_file_to_drive(manifest_path, p["drive_root"], drive_p["drive_root"])
                print(f"[inpi] synced archive to Drive: {local_path.name}")
        print("[inpi] download phase done")


def download_with_retries(
    conn: InpiConnector,
    remote_path: str,
    local_path: Path,
    *,
    size: int,
    overwrite: bool,
    retries: int,
    drive_root: Path | None = None,
    local_root: Path | None = None,
) -> bool:
    attempts = max(retries, 1)
    for attempt in range(1, attempts + 1):
        try:
            conn.download(remote_path, local_path, size=size, overwrite=overwrite and attempt == 1)
            return True
        except (TimeoutError, socket.timeout, OSError, ftplib.Error) as exc:
            if local_path.exists() and (not size or local_path.stat().st_size == size):
                print(f"[inpi] archive completed despite connection error: {local_path.name}")
                return True
            if drive_root is not None and local_root is not None:
                sync_partial_to_drive(local_path, local_root, drive_root)
            if attempt >= attempts:
                raise
            wait_seconds = min(30 * attempt, 120)
            print(
                f"[inpi] retry {attempt + 1}/{attempts} after connection error on "
                f"{local_path.name}: {exc}; waiting {wait_seconds}s"
            )
            time.sleep(wait_seconds)
            conn.reconnect()
    return False


def seed_partial_from_drive(local_path: Path, local_root: Path, drive_root: Path) -> bool:
    local_part = local_path.with_suffix(local_path.suffix + ".part")
    drive_part = (drive_root / local_path.relative_to(local_root)).with_suffix(local_path.suffix + ".part")
    if not drive_part.exists():
        return False
    if local_part.exists() and local_part.stat().st_size >= drive_part.stat().st_size:
        return False
    local_part.parent.mkdir(parents=True, exist_ok=True)
    if local_path.exists() and local_path.stat().st_size < drive_part.stat().st_size:
        local_path.unlink()
    shutil.copy2(drive_part, local_part)
    return True


def sync_partial_to_drive(local_path: Path, local_root: Path, drive_root: Path) -> None:
    local_part = local_path.with_suffix(local_path.suffix + ".part")
    if not local_part.exists():
        return
    drive_part = (drive_root / local_path.relative_to(local_root)).with_suffix(local_path.suffix + ".part")
    if drive_part.exists() and drive_part.stat().st_size >= local_part.stat().st_size:
        return
    drive_part.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(local_part, drive_part)
    print(f"[inpi] synced partial to Drive: {drive_part.name} ({drive_part.stat().st_size / 1024 / 1024:,.1f} MB)")


def remove_drive_partial(local_path: Path, local_root: Path, drive_root: Path) -> None:
    drive_part = (drive_root / local_path.relative_to(local_root)).with_suffix(local_path.suffix + ".part")
    if drive_part.exists():
        drive_part.unlink()
        print(f"[inpi] removed stale Drive partial: {drive_part.name}")


def discover(conn: InpiConnector, base: str, *, categories: set[str], niveaux: set[str]) -> list[RemoteArchive]:
    archives = []
    scanned = 0
    for remote_path, size, mtime in conn.walk(base or "/"):
        scanned += 1
        if scanned == 1 or scanned % 500 == 0:
            print(f"[inpi] scanned files={scanned} matches={len(archives)} latest={remote_path}")
        target = detect_target(remote_path)
        if target is None:
            continue
        category, niveau = target
        if categories and category not in categories:
            continue
        if niveaux and niveau not in niveaux:
            continue
        archives.append(RemoteArchive(remote_path, size, mtime, category, niveau))
        if len(archives) % 50 == 0:
            print(f"[inpi] matching archives={len(archives)} scanned={scanned}")
    print(f"[inpi] discovery done scanned={scanned} matches={len(archives)}")
    return sorted(archives, key=lambda item: item.path)


def detect_target(path: str) -> tuple[str, str] | None:
    lower = path.lower()
    if not lower.endswith(".zip"):
        return None
    normalized = lower.replace("-", "_").replace(" ", "_")
    category = None
    if "formalites" in normalized or "formalite" in normalized:
        category = "formalites"
    if "comptes_annuels" in normalized or "compte_annuel" in normalized or "comptesannuels" in normalized:
        category = "comptes_annuels"
    if category is None:
        return None
    niveau = "niveau1" if any(token in normalized for token in ("niveau_1", "niveau1", "niv_1", "niv1")) else "standard"
    return category, niveau


def local_path_for(base: Path, remote_path: str) -> Path:
    rel = PurePosixPath(remote_path.lstrip("/"))
    return base / Path(*rel.parts)


def _split_filter(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def _join_posix(base: str, name: str) -> str:
    return f"{base.rstrip('/')}/{name}"


def _ftp_is_dir(ftp: ftplib.FTP, path: str, facts: dict, use_mlsd: bool) -> bool:
    if use_mlsd:
        ftype = (facts.get("type") or "").lower()
        if ftype in ("dir", "cdir", "pdir"):
            return True
        if ftype == "file":
            return False
    cwd = ftp.pwd()
    try:
        ftp.cwd(path)
        ftp.cwd(cwd)
        return True
    except ftplib.error_perm:
        return False


def _ftp_size(ftp: ftplib.FTP, path: str) -> int:
    try:
        ftp.voidcmd("TYPE I")
        return int(ftp.size(path) or 0)
    except Exception:
        return 0


def _ftp_mdtm(ftp: ftplib.FTP, path: str) -> datetime | None:
    try:
        response = ftp.sendcmd(f"MDTM {path}")
    except Exception:
        return None
    parts = response.split()
    if len(parts) >= 2:
        return _parse_mlsd_modify(parts[1])
    return None


def _parse_mlsd_modify(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _print_progress(name: str, written: int, total: int, started: float) -> None:
    elapsed = max(time.monotonic() - started, 1.0)
    mb = written / 1024 / 1024
    speed = mb / elapsed
    if total:
        print(f"[inpi] {name}: {mb:,.1f} MB / {total / 1024 / 1024:,.1f} MB ({written / total * 100:.2f}%), {speed:.1f} MB/s")
    else:
        print(f"[inpi] {name}: {mb:,.1f} MB, {speed:.1f} MB/s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download INPI source ZIP archives in Colab.")
    parser.add_argument("--drive-root", default=DEFAULT_DRIVE_ROOT)
    parser.add_argument("--work-dir", help="Optional fast local staging root, for example /content/pfe_work.")
    parser.add_argument("--repo-dir", default=".")
    parser.add_argument("--install-deps", action="store_true")
    parser.add_argument("--protocol", default=os.getenv("INPI_FTP_PROTOCOL", "ftp"), choices=("ftp", "sftp"))
    parser.add_argument("--host", default=os.getenv("INPI_FTP_HOST", ""))
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--user", default=os.getenv("INPI_FTP_USER", ""))
    parser.add_argument("--password", default=os.getenv("INPI_FTP_PASSWORD", ""))
    parser.add_argument("--remote-base-dir", default=os.getenv("INPI_REMOTE_BASE_DIR", "/"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("INPI_FTP_TIMEOUT", "600")))
    parser.add_argument("--categories", help="Comma-separated: comptes_annuels,formalites")
    parser.add_argument("--niveaux", help="Comma-separated: standard,niveau1")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--retries", type=int, default=int(os.getenv("INPI_DOWNLOAD_RETRIES", "4")))
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    main()
