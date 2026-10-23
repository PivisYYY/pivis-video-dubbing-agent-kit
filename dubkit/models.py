"""Pinned speech-model registry and local-cache resolution.

Responsibilities (and nothing else):

1. ``load_registry()`` — read the machine-readable pin list from
   ``models.json`` at the repository root (never from user config).
2. ``resolve_model(alias, ...)`` — make one pinned model available on disk
   through ``huggingface_hub.snapshot_download`` and verify its integrity.
   Nothing is downloaded unless ``accept_download=True`` is passed explicitly.
3. ``model_status()`` — read-only report of what is already in the local
   Hugging Face cache; it never triggers a download.

Design rules (enforced here, restated in AGENTS.md):

- Revisions are pinned in ``models.json``; this module never upgrades a
  revision or silently re-resolves to a moving ref.
- A model missing from the local cache is a hard error when offline; the
  module never falls back to the network on its own.
- Integrity failures are hard errors; the module never fakes success.

All exceptions subclass ``ValueError`` or ``FileNotFoundError`` so the CLI's
user-facing error rendering (which catches ``ValueError``/``OSError``)
prints them as clean JSON errors instead of tracebacks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

__all__ = [
    "REGISTRY_PATH",
    "DubkitModelError",
    "RegistryError",
    "UnknownModelAliasError",
    "ModelNotCachedError",
    "ModelIntegrityError",
    "ModelDownloadError",
    "load_registry",
    "resolve_model",
    "model_status",
]

# models.json lives at the repository root: <repo>/dubkit/models.py -> parents[1].
REGISTRY_PATH = Path(__file__).resolve().parents[1] / "models.json"

_REQUIRED_ALIASES = ("asr", "tts", "custom_tts")

# huggingface_hub raises these (by class name) when local_files_only=True and
# the snapshot/revision is not in the local cache. Matched by name so this
# module works across huggingface_hub versions without importing them.
_MISSING_LOCALLY_EXC_NAMES = frozenset(
    {"LocalEntryNotFoundError", "EntryNotFoundError", "RevisionNotFoundError", "IncompleteSnapshotError"}
)

# Lazily bound to huggingface_hub.snapshot_download on first use. Tests
# replace this attribute with a fake; production code goes through
# _get_snapshot_download().
_snapshot_download = None


class DubkitModelError(ValueError):
    """Base class for registry and model-resolution failures."""


class RegistryError(DubkitModelError):
    """models.json is missing, unreadable or violates the expected schema."""


class UnknownModelAliasError(DubkitModelError):
    """Alias is not one of the pinned registry entries."""


class ModelNotCachedError(DubkitModelError, FileNotFoundError):
    """Pinned model is absent from the local cache and downloads are off."""


class ModelIntegrityError(DubkitModelError):
    """Local snapshot exists but fails the pinned file-layout check."""


class ModelDownloadError(DubkitModelError):
    """huggingface_hub could not resolve/download the pinned model."""


def _get_snapshot_download():
    """Bind and cache huggingface_hub.snapshot_download on first use."""
    global _snapshot_download
    if _snapshot_download is None:
        try:
            from huggingface_hub import snapshot_download
        except Exception as exc:  # ImportError or a broken installation
            raise ModelDownloadError(
                "huggingface_hub is required but not importable; bootstrap the "
                "project with ./bootstrap.sh (the 'speech' extra provides "
                "huggingface-hub>=0.30,<2)"
            ) from exc
        _snapshot_download = snapshot_download
    return _snapshot_download


def load_registry() -> dict:
    """Return the inner ``models`` mapping of the repo-root ``models.json``.

    Raises :class:`RegistryError` when the file is missing, unreadable or
    does not match schema_version 1 with the required pinned aliases.
    """
    try:
        raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RegistryError(f"model registry not found at {REGISTRY_PATH}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f"could not read model registry {REGISTRY_PATH}: {exc}") from exc

    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise RegistryError(f"{REGISTRY_PATH}: unsupported schema_version (expected integer 1)")

    models = raw.get("models")
    if not isinstance(models, dict) or not models:
        raise RegistryError(f"{REGISTRY_PATH}: 'models' must be a non-empty mapping")

    for alias in _REQUIRED_ALIASES:
        entry = models.get(alias)
        if not isinstance(entry, dict):
            raise RegistryError(f"{REGISTRY_PATH}: models.{alias} must be a mapping")
        for field in ("repo_id", "revision"):
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                raise RegistryError(
                    f"{REGISTRY_PATH}: models.{alias}.{field} must be a non-empty string"
                )
    return models


def resolve_model(
    alias: str,
    *,
    accept_download: bool = False,
    cache_dir: Union[str, Path, None] = None,
) -> Path:
    """Return the verified local snapshot path for one pinned model alias.

    Uses ``huggingface_hub.snapshot_download(repo_id, revision, cache_dir,
    local_files_only)`` with the exact pinned ``repo_id``/``revision`` from
    ``models.json``. With ``accept_download=False`` (the default) the lookup
    is strictly offline: a cache miss raises :class:`ModelNotCachedError`
    instead of touching the network. With ``accept_download=True`` a download
    is authorized by the caller — pass that flag only after the user has
    explicitly agreed.

    The returned path is validated against the pinned file layout (config,
    weights, and for TTS the speech_tokenizer directory); a snapshot that
    fails validation raises :class:`ModelIntegrityError` even if
    ``snapshot_download`` returned successfully.
    """
    models = load_registry()
    if alias not in models:
        raise UnknownModelAliasError(
            f"unknown model alias {alias!r}; valid aliases: {', '.join(models)}"
        )
    entry = models[alias]

    downloader = _get_snapshot_download()
    kwargs: dict = {
        "repo_id": entry["repo_id"],
        "revision": entry["revision"],
        "local_files_only": not accept_download,
    }
    if cache_dir is not None:
        kwargs["cache_dir"] = str(cache_dir)

    try:
        snapshot = downloader(**kwargs)
    except Exception as exc:
        if not accept_download and type(exc).__name__ in _MISSING_LOCALLY_EXC_NAMES:
            raise ModelNotCachedError(
                f"model '{alias}' ({entry['repo_id']}@{entry['revision']}) is not in the "
                "local Hugging Face cache; nothing was downloaded. After explicit "
                "authorization run: python -m dubkit models fetch --accept-download"
            ) from exc
        raise ModelDownloadError(
            f"could not resolve model '{alias}' ({entry['repo_id']}@{entry['revision']}) "
            f"with accept_download={accept_download}: {type(exc).__name__}: {exc}"
        ) from exc

    snapshot_path = Path(snapshot)
    _validate_snapshot(alias, entry, snapshot_path)
    return snapshot_path


def model_status(*, cache_dir: Union[str, Path, None] = None) -> dict:
    """Read-only availability report for every pinned alias.

    Inspects the local Hugging Face cache only (``local_files_only=True``
    underneath); it never downloads, never writes and never upgrades a
    revision. Each alias maps to a dict with ``available``, ``repo_id``,
    ``revision``, ``license``, ``path`` and, when unavailable, a ``detail``
    explaining why.
    """
    models = load_registry()
    report: dict = {}
    for alias in _REQUIRED_ALIASES:
        entry = models[alias]
        info = {
            "repo_id": entry["repo_id"],
            "revision": entry["revision"],
            "license": entry.get("license"),
            "available": False,
            "path": None,
            "detail": None,
        }
        try:
            path = resolve_model(alias, accept_download=False, cache_dir=cache_dir)
            info["available"] = True
            info["path"] = str(path)
        except ModelNotCachedError:
            info["detail"] = (
                "not downloaded; run 'python -m dubkit models fetch --accept-download' "
                "after explicit authorization"
            )
        except DubkitModelError as exc:  # integrity failure, hub missing, ...
            info["detail"] = str(exc)
        report[alias] = info
    return report


def _validate_snapshot(alias: str, entry: dict, path: Path) -> None:
    """Check a downloaded snapshot against the pinned file layout."""
    if not path.is_dir():
        raise ModelIntegrityError(
            f"model '{alias}' snapshot path is not a directory: {path}"
        )

    problems: list[str] = []
    spec = entry.get("integrity") or {}
    for rel in spec.get("required", []):
        file = path / rel
        if not file.is_file() or file.stat().st_size == 0:
            problems.append(f"missing or empty file {rel}")
        elif file.suffix == '.json':
            try:
                json.loads(file.read_text(encoding='utf-8'))
            except (ValueError, OSError):
                problems.append(f"invalid JSON config {rel}")
    for group in spec.get("groups", []):
        alternatives = group.get("any_of") or []
        if alternatives and not any((path / pat).is_file() and (path / pat).stat().st_size > 0 for pat in alternatives):
            problems.append(
                "missing weights (need one of: " + " | ".join(alternatives) + ")"
            )
    problems.extend(_index_shard_problems(path))

    if problems:
        raise ModelIntegrityError(
            f"model '{alias}' ({entry['repo_id']}@{entry['revision']}) failed local "
            f"integrity check at {path}: " + "; ".join(problems)
            + ". Restore the snapshot with 'python -m dubkit models fetch "
              "--accept-download' after explicit authorization; do not run "
              "inference against an incomplete snapshot."
        )


def _index_shard_problems(path: Path) -> list[str]:
    """Verify shards referenced by any present safetensors weight index.

    An index is only validated when it is actually present — models using a
    single weight file never get an index requirement.
    """
    problems: list[str] = []
    for index_path in sorted(path.rglob("*safetensors.index.json")):
        rel = index_path.relative_to(path)
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"unreadable weight index {rel}: {exc}")
            continue
        weight_map = index.get("weight_map")
        if not isinstance(weight_map, dict) or not weight_map:
            problems.append(f"weight index {rel} has no usable weight_map")
            continue
        for shard in sorted(set(weight_map.values())):
            if Path(shard).is_absolute() or '..' in Path(shard).parts:
                problems.append(f"weight index {rel} contains an unsafe shard path")
            elif not (index_path.parent / shard).is_file() or (index_path.parent / shard).stat().st_size == 0:
                problems.append(f"weight index {rel} references missing or empty shard {shard}")
    return problems
