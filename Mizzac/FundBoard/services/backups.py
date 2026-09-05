"""Verified database backups; restoration always targets a new database."""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.db import connections

MANIFEST_VERSION = "1.0"
SQLITE_SUFFIX = ".sqlite3"
POSTGRES_SUFFIX = ".dump"


class BackupError(RuntimeError):
    pass


@dataclass(frozen=True)
class BackupVerification:
    backup_path: Path
    engine: str
    sha256: str
    size: int
    integrity: str
    table_count: int
    migration_count: int


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def manifest_path(backup_path):
    path = Path(backup_path)
    return path.with_name(f"{path.name}.manifest.json")


def _safe_destination(destination):
    directory = Path(destination).expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        raise BackupError("Le dossier de sauvegarde doit déjà exister.")
    return directory


def _safe_label(label):
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-_")
    return normalized[:40] or "mizzac"


def _backup_name(label, suffix):
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{_safe_label(label)}-{stamp}-{uuid.uuid4().hex[:8]}{suffix}"


def _sqlite_inventory(database_path):
    try:
        database = sqlite3.connect(f"{Path(database_path).resolve().as_uri()}?mode=ro", uri=True)
        integrity = database.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_issues = database.execute("PRAGMA foreign_key_check").fetchall()
        tables = [
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        migrations = [
            f"{app}.{name}"
            for app, name in database.execute(
                "SELECT app, name FROM django_migrations ORDER BY app, name"
            )
        ]
        counts = {
            table: database.execute(
                f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34) * 2)}"'
            ).fetchone()[0]
            for table in tables
        }
    except (sqlite3.Error, OSError) as exc:
        raise BackupError("La sauvegarde SQLite est illisible ou incomplète.") from exc
    finally:
        if "database" in locals():
            database.close()
    if integrity != "ok" or foreign_key_issues:
        raise BackupError("Le contrôle d'intégrité SQLite a échoué.")
    return integrity, migrations, counts


def _write_manifest(backup_path, *, engine, migrations, table_counts):
    backup_path = Path(backup_path)
    payload = {
        "schema_version": MANIFEST_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "engine": engine,
        "filename": backup_path.name,
        "sha256": sha256_file(backup_path),
        "size": backup_path.stat().st_size,
        "migrations": list(migrations),
        "table_counts": dict(table_counts),
    }
    output = manifest_path(backup_path)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(output, 0o600)
    return output


def create_sqlite_backup(source, destination, *, label="mizzac"):
    source = Path(source).expanduser().resolve()
    directory = _safe_destination(destination)
    if not source.exists() or not source.is_file():
        raise BackupError("La base SQLite source est introuvable.")
    output = directory / _backup_name(label, SQLITE_SUFFIX)
    temporary = output.with_name(f".{output.name}.partial")
    try:
        source_db = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
        target_db = sqlite3.connect(temporary)
        with target_db:
            source_db.backup(target_db)
        target_db.close()
        source_db.close()
        os.chmod(temporary, 0o600)
        temporary.replace(output)
        _, migrations, counts = _sqlite_inventory(output)
        _write_manifest(
            output,
            engine="sqlite",
            migrations=migrations,
            table_counts=counts,
        )
    except Exception:
        if temporary.exists():
            temporary.unlink()
        if output.exists() and not manifest_path(output).exists():
            output.unlink()
        raise
    return output


def _postgres_command(configuration, output):
    command = ["pg_dump", "--format=custom", "--file", str(output)]
    for option, key in (
        ("--host", "HOST"),
        ("--port", "PORT"),
        ("--username", "USER"),
    ):
        if configuration.get(key):
            command.extend([option, str(configuration[key])])
    command.append(str(configuration["NAME"]))
    return command


def create_postgresql_backup(configuration, destination, *, label="mizzac"):
    directory = _safe_destination(destination)
    output = directory / _backup_name(label, POSTGRES_SUFFIX)
    environment = os.environ.copy()
    if configuration.get("PASSWORD"):
        environment["PGPASSWORD"] = str(configuration["PASSWORD"])
    try:
        subprocess.run(
            _postgres_command(configuration, output),
            check=True,
            capture_output=True,
            text=True,
            env=environment,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        if output.exists():
            output.unlink()
        raise BackupError("pg_dump n'a pas pu créer la sauvegarde PostgreSQL.") from exc
    os.chmod(output, 0o600)
    recorder = connections["default"].introspection.django_table_names(only_existing=True)
    _write_manifest(output, engine="postgresql", migrations=[], table_counts={name: -1 for name in recorder})
    return output


def create_database_backup(destination, *, label="mizzac"):
    connection = connections["default"]
    configuration = settings.DATABASES["default"]
    if connection.vendor == "sqlite":
        connection.close()
        name = configuration["NAME"]
        if str(name) == ":memory:":
            raise BackupError("Une base SQLite en mémoire ne peut pas être sauvegardée.")
        return create_sqlite_backup(name, destination, label=label)
    if connection.vendor == "postgresql":
        return create_postgresql_backup(configuration, destination, label=label)
    raise BackupError("Ce moteur de base de données n'est pas pris en charge.")


def _load_manifest(backup_path):
    path = manifest_path(backup_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError("Le manifeste de sauvegarde est absent ou invalide.") from exc
    required = {"schema_version", "engine", "filename", "sha256", "size"}
    if payload.keys() < required or payload["schema_version"] != MANIFEST_VERSION:
        raise BackupError("Le manifeste de sauvegarde n'est pas compatible.")
    return payload


def verify_database_backup(backup_path):
    backup = Path(backup_path).expanduser().resolve()
    if not backup.exists() or not backup.is_file():
        raise BackupError("La sauvegarde est introuvable.")
    manifest = _load_manifest(backup)
    checksum = sha256_file(backup)
    if (
        manifest["filename"] != backup.name
        or manifest["sha256"] != checksum
        or manifest["size"] != backup.stat().st_size
    ):
        raise BackupError("La taille ou l'empreinte de la sauvegarde ne correspond pas.")
    if manifest["engine"] == "sqlite":
        integrity, migrations, counts = _sqlite_inventory(backup)
        if manifest.get("migrations") != migrations or manifest.get("table_counts") != counts:
            raise BackupError("L'inventaire restauré diffère du manifeste.")
    elif manifest["engine"] == "postgresql":
        try:
            subprocess.run(
                ["pg_restore", "--list", str(backup)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise BackupError("pg_restore ne reconnaît pas cette sauvegarde.") from exc
        integrity, migrations, counts = "archive-readable", [], manifest.get("table_counts", {})
    else:
        raise BackupError("Le moteur indiqué dans le manifeste est inconnu.")
    return BackupVerification(
        backup_path=backup,
        engine=manifest["engine"],
        sha256=checksum,
        size=backup.stat().st_size,
        integrity=integrity,
        table_count=len(counts),
        migration_count=len(migrations),
    )


def restore_sqlite_backup(backup_path, destination):
    verification = verify_database_backup(backup_path)
    if verification.engine != "sqlite":
        raise BackupError("La restauration automatisée accepte uniquement SQLite.")
    destination = Path(destination).expanduser().resolve()
    if destination.exists():
        raise BackupError("La destination existe déjà ; aucune donnée ne sera écrasée.")
    if not destination.parent.exists() or not destination.parent.is_dir():
        raise BackupError("Le dossier de destination doit déjà exister.")
    configured = settings.DATABASES["default"]["NAME"]
    if str(configured) != ":memory:" and Path(configured).expanduser().resolve() == destination:
        raise BackupError("La restauration directe sur la base active est interdite.")
    temporary = destination.with_name(f".{destination.name}.partial")
    try:
        shutil.copyfile(verification.backup_path, temporary)
        os.chmod(temporary, 0o600)
        temporary.replace(destination)
        _sqlite_inventory(destination)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        if destination.exists():
            destination.unlink()
        raise
    return destination
