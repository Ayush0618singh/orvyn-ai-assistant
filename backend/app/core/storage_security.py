
from __future__ import annotations

import os
from pathlib import Path


class UnsafeStoragePathError(ValueError):
    """Raised when a storage path escapes its permitted root."""


def resolve_storage_root(root: str | Path) -> Path:
    """Resolve the configured storage root to an absolute path."""
    if not isinstance(root, (str, Path)):
        raise UnsafeStoragePathError("Invalid storage root.")

    if not str(root).strip():
        raise UnsafeStoragePathError("Storage root cannot be empty.")

    try:
        path = Path(root).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise UnsafeStoragePathError(
            "Storage root could not be resolved."
        ) from exc

    if not path.is_absolute():
        raise UnsafeStoragePathError(
            "Storage root must be an absolute path."
        )

    return path


def _validate_single_path_component(
    value: str,
    *,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value.strip():
        raise UnsafeStoragePathError(
            f"Invalid {field_name}."
        )

    if value in {".", ".."}:
        raise UnsafeStoragePathError(
            f"Invalid {field_name}."
        )

    if "/" in value or "\\" in value:
        raise UnsafeStoragePathError(
            f"{field_name.capitalize()} must be a single path component."
        )

    if "\x00" in value:
        raise UnsafeStoragePathError(
            f"Invalid {field_name}."
        )

    if Path(value).name != value:
        raise UnsafeStoragePathError(
            f"Invalid {field_name}."
        )


def resolve_user_storage_dir(
    root: str | Path,
    user_id: str,
) -> Path:
    """Resolve a user's directory without allowing traversal."""
    _validate_single_path_component(
        user_id,
        field_name="user identifier",
    )

    storage_root = resolve_storage_root(root)

    try:
        user_dir = (storage_root / user_id).resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise UnsafeStoragePathError(
            "User storage directory could not be resolved."
        ) from exc

    if user_dir.parent != storage_root:
        raise UnsafeStoragePathError(
            "User storage directory escapes the storage root."
        )

    return user_dir


def resolve_storage_file(
    root: str | Path,
    user_id: str,
    stored_name: str,
) -> Path:
    """Resolve a stored file while enforcing user-directory containment."""
    _validate_single_path_component(
        stored_name,
        field_name="stored filename",
    )

    user_dir = resolve_user_storage_dir(root, user_id)

    try:
        file_path = (user_dir / stored_name).resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as exc:
        raise UnsafeStoragePathError(
            "Storage file path could not be resolved."
        ) from exc

    if file_path.parent != user_dir:
        raise UnsafeStoragePathError(
            "Attachment path escapes the user storage directory."
        )

    return file_path


def resolve_existing_storage_path(
    root: str | Path,
    user_id: str,
    stored_name: str,
    recorded_path: str | Path,
) -> Path:
    """Validate a database-recorded path against its expected location."""
    expected = resolve_storage_file(
        root,
        user_id,
        stored_name,
    )

    try:
        recorded = Path(recorded_path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise UnsafeStoragePathError(
            "Recorded attachment path is invalid."
        ) from exc

    if recorded != expected:
        raise UnsafeStoragePathError(
            "Recorded attachment path does not match its expected location."
        )

    return expected
