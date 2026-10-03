"""Lokale unveränderliche Artefakte und atomische Zustandsupdates."""
from __future__ import annotations

import contextlib
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
import sys


class Blocked(RuntimeError):
    pass


def repo_root() -> Path:
    configured = os.environ.get("MA_REPO_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    source = Path(__file__).resolve().parents[2]
    if (source / "schemas").is_dir():
        return source
    installed = Path(sys.prefix) / "share" / "medizinanders"
    if (installed / "schemas").is_dir():
        return installed
    raise Blocked("Pipeline-Ressourcen fehlen. Im Repository: python3 -m pip install -e .")


def data_root() -> Path:
    root = Path(os.environ.get("MA_DATA_DIR", "~/.local/share/medizinanders")).expanduser().resolve()
    # Produktionsdaten sind im Repository auch mit versehentlichem git add sicher ausgeschlossen.
    repo = repo_root()
    if root == repo or repo in root.parents:
        raise Blocked("MA_DATA_DIR muss außerhalb des Pipeline-Repositories liegen.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def ensure_contained(base: Path, path: Path) -> Path:
    resolved_base, resolved = base.resolve(), path.resolve()
    if resolved != resolved_base and resolved_base not in resolved.parents:
        raise Blocked("Ein Speicherpfad/Symlink verlässt den zulässigen externen Datenspeicher.")
    repo = repo_root()
    if resolved == repo or repo in resolved.parents:
        raise Blocked("Produktionsdaten dürfen auch über Symlinks nicht ins Repository gelangen.")
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise Blocked("Symlinks in Produktionspfaden sind unzulässig; tatsächliche lokale Dateien verwenden.")
        if candidate.absolute() == base.absolute():
            break
    return resolved


def ensure_project_storage(root: Path) -> Path:
    """Reject redirected descendants before any production mutation."""
    root = ensure_contained(data_root(), root)
    for path in root.rglob("*"):
        if path.is_symlink():
            ensure_contained(root, path)
    return root


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def object_hash(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def read_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        def reject_constant(value):
            raise Blocked(f"Nicht-JSON-konformer Zahlenwert: {value}")
        return json.load(stream, parse_constant=reject_constant)


def atomic_json(path: Path, value, exclusive=False):
    path = ensure_contained(data_root(), path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    blob = canonical(value)
    if exclusive:
        created = False
        try:
            with path.open("xb") as stream:
                created = True
                stream.write(blob)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            if created:
                path.unlink(missing_ok=True)
            raise
        return
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=".write-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_text(path: Path, content: str):
    path = ensure_contained(data_root(), path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(content, encoding="utf-8")


@contextlib.contextmanager
def lock(path: Path):
    path = ensure_contained(data_root(), path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def project_path(project_id: str) -> Path:
    if not re.fullmatch(r"MA-\d{8}-\d{3}", project_id):
        raise Blocked("Projekt-ID muss MA-YYYYMMDD-NNN entsprechen.")
    base = data_root()
    path = ensure_contained(base, base / "projects" / project_id)
    if not (path / "state.json").is_file():
        raise Blocked(f"Projekt nicht gefunden: {project_id}")
    return ensure_project_storage(path)


def artifact_path(root: Path, ref: dict) -> Path:
    aid, version = ref["artefakt_id"], ref["version"]
    if not re.fullmatch(r"A(?:0[1-9]|1[0-2])", aid) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise Blocked("Ungültige Artefaktreferenz.")
    return ensure_contained(root, root / "artifacts" / aid / f"{version}.json")


def reference(root: Path, aid: str, version: str) -> dict:
    path = artifact_path(root, {"artefakt_id": aid, "version": version})
    return {"artefakt_id": aid, "version": version, "sha256": digest(path)}


def current(root: Path, state: dict, aid: str) -> dict:
    ref = state["artifacts"].get(aid)
    if not ref:
        raise Blocked(f"{aid} fehlt oder wurde invalidiert.")
    path = artifact_path(root, ref)
    if not path.is_file() or digest(path) != ref["sha256"]:
        raise Blocked(f"{aid}: Hash stimmt nicht. Niemals Artefakte direkt bearbeiten; ma invalidate/ma import verwenden.")
    return read_json(path)
