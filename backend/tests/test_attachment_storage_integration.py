
from pathlib import Path

import pytest

from app.core.storage_security import (
    UnsafeStoragePathError,
    resolve_existing_storage_path,
    resolve_storage_file,
)


def test_attachment_file_cannot_escape_user_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_storage_file(
            tmp_path,
            "user-a",
            "../user-b/private.pdf",
        )


def test_symlink_escape_is_rejected_when_supported(
    tmp_path: Path,
) -> None:
    root = tmp_path / "uploads"
    user_dir = root / "user-a"
    outside_dir = tmp_path / "outside"

    user_dir.mkdir(parents=True)
    outside_dir.mkdir()

    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("private", encoding="utf-8")

    link = user_dir / "linked.txt"

    try:
        link.symlink_to(outside_file)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is unavailable on this system.")

    with pytest.raises(UnsafeStoragePathError):
        resolve_existing_storage_path(
            root,
            "user-a",
            "linked.txt",
            link,
        )


def test_rejects_database_path_mismatch(
    tmp_path: Path,
) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_existing_storage_path(
            tmp_path,
            "user-a",
            "stored.pdf",
            tmp_path / "user-a" / "different.pdf",
        )
