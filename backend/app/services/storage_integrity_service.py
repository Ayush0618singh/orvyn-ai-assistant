
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from app.core.storage_security import (
    UnsafeStoragePathError,
    resolve_storage_file,
    resolve_storage_root,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StorageIntegrityIssue:
    """One detected storage integrity issue."""

    category: str
    user_id: str
    stored_name: str
    detail: str


@dataclass(frozen=True, slots=True)
class StorageIntegrityReport:
    """Immutable, read-only storage integrity report."""

    checked_records: int
    valid_files: int
    issues: tuple[StorageIntegrityIssue, ...]

    @property
    def is_healthy(self) -> bool:
        return not self.issues


def audit_attachment_storage(
    *,
    storage_root: str | Path,
    records: Iterable[tuple[str, str, str | Path]],
) -> StorageIntegrityReport:
    """Audit attachment records against the configured storage directory.

    Each record must contain:
        (user_id, stored_name, recorded_path)

    The audit never deletes files or modifies database records.
    """
    root = resolve_storage_root(storage_root)

    checked_records = 0
    valid_files = 0
    issues: list[StorageIntegrityIssue] = []
    known_paths: set[Path] = set()

    for user_id, stored_name, recorded_path in records:
        checked_records += 1

        try:
            expected_path = resolve_storage_file(
                root,
                user_id,
                stored_name,
            )

            recorded = Path(recorded_path).expanduser().resolve(
                strict=False
            )

            if recorded != expected_path:
                raise UnsafeStoragePathError(
                    "Recorded path differs from the expected path."
                )

            user_dir = expected_path.parent

            if user_dir.parent != root:
                raise UnsafeStoragePathError(
                    "Resolved path is outside the configured storage root."
                )

            if user_dir.is_symlink() or expected_path.is_symlink():
                raise UnsafeStoragePathError(
                    "Symbolic links are not permitted for stored attachments."
                )

            if not expected_path.is_file():
                issues.append(
                    StorageIntegrityIssue(
                        category="missing_file",
                        user_id=str(user_id),
                        stored_name=str(stored_name),
                        detail=(
                            "Database record has no matching regular file."
                        ),
                    )
                )
                continue

            known_paths.add(expected_path)
            valid_files += 1

        except (UnsafeStoragePathError, OSError, TypeError, ValueError) as exc:
            logger.warning(
                "Attachment storage integrity issue detected "
                "for user_id=%r stored_name=%r",
                user_id,
                stored_name,
            )

            issues.append(
                StorageIntegrityIssue(
                    category="unsafe_path",
                    user_id=str(user_id),
                    stored_name=str(stored_name),
                    detail=str(exc),
                )
            )

    if root.exists() and root.is_dir() and not root.is_symlink():
        try:
            for user_dir in root.iterdir():
                if user_dir.is_symlink() or not user_dir.is_dir():
                    continue

                for candidate in user_dir.iterdir():
                    if candidate.is_symlink() or not candidate.is_file():
                        continue

                    resolved_candidate = candidate.resolve(strict=False)

                    if resolved_candidate not in known_paths:
                        issues.append(
                            StorageIntegrityIssue(
                                category="untracked_file",
                                user_id=user_dir.name,
                                stored_name=candidate.name,
                                detail=(
                                    "File exists in storage but was not "
                                    "matched to a valid database record."
                                ),
                            )
                        )

        except OSError:
            logger.exception(
                "Could not complete attachment storage directory audit."
            )

            issues.append(
                StorageIntegrityIssue(
                    category="audit_io_error",
                    user_id="",
                    stored_name="",
                    detail=(
                        "Storage directory could not be fully inspected."
                    ),
                )
            )

    return StorageIntegrityReport(
        checked_records=checked_records,
        valid_files=valid_files,
        issues=tuple(issues),
    )
