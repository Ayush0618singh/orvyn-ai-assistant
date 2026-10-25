
from pathlib import Path

import pytest

from app.core.storage_security import (
    UnsafeStoragePathError,
    resolve_existing_storage_path,
    resolve_storage_file,
    resolve_user_storage_dir,
)


def test_user_directory_is_inside_storage_root(tmp_path: Path) -> None:
    result = resolve_user_storage_dir(tmp_path, "user-123")

    assert result == (tmp_path / "user-123").resolve()
    assert result.parent == tmp_path.resolve()


@pytest.mark.parametrize(
    "user_id",
    [
        "",
        " ",
        ".",
        "..",
        "../other-user",
        "user/other",
        r"user\other",
    ],
)
def test_rejects_unsafe_user_id(
    tmp_path: Path,
    user_id: str,
) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_user_storage_dir(tmp_path, user_id)


def test_resolves_safe_filename(tmp_path: Path) -> None:
    result = resolve_storage_file(
        tmp_path,
        "user-123",
        "c7c3d1.jpg",
    )

    assert result == (
        tmp_path / "user-123" / "c7c3d1.jpg"
    ).resolve()


@pytest.mark.parametrize(
    "filename",
    [
        "",
        ".",
        "..",
        "../secret.txt",
        "folder/file.txt",
        r"folder\file.txt",
        "/etc/passwd",
    ],
)
def test_rejects_unsafe_filename(
    tmp_path: Path,
    filename: str,
) -> None:
    with pytest.raises(UnsafeStoragePathError):
        resolve_storage_file(
            tmp_path,
            "user-123",
            filename,
        )


def test_rejects_recorded_path_outside_expected_directory(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "other-user" / "secret.txt"

    with pytest.raises(UnsafeStoragePathError):
        resolve_existing_storage_path(
            tmp_path,
            "user-123",
            "stored.txt",
            outside,
        )


def test_accepts_matching_recorded_path(
    tmp_path: Path,
) -> None:
    expected = (
        tmp_path / "user-123" / "stored.txt"
    ).resolve()

    result = resolve_existing_storage_path(
        tmp_path,
        "user-123",
        "stored.txt",
        expected,
    )

    assert result == expected
