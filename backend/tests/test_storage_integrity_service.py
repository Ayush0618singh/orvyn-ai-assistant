
from pathlib import Path

from app.services.storage_integrity_service import (
    audit_attachment_storage,
)


def test_audit_reports_healthy_storage(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    user_dir = root / "user-a"
    user_dir.mkdir(parents=True)

    stored_file = user_dir / "document.txt"
    stored_file.write_text("private document", encoding="utf-8")

    report = audit_attachment_storage(
        storage_root=root,
        records=[
            ("user-a", "document.txt", stored_file),
        ],
    )

    assert report.checked_records == 1
    assert report.valid_files == 1
    assert report.issues == ()
    assert report.is_healthy


def test_audit_reports_missing_file(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    (root / "user-a").mkdir(parents=True)

    expected_path = root / "user-a" / "missing.txt"

    report = audit_attachment_storage(
        storage_root=root,
        records=[
            ("user-a", "missing.txt", expected_path),
        ],
    )

    assert report.checked_records == 1
    assert report.valid_files == 0
    assert any(
        issue.category == "missing_file"
        for issue in report.issues
    )


def test_audit_reports_untracked_file(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    user_dir = root / "user-a"
    user_dir.mkdir(parents=True)

    orphan = user_dir / "orphan.txt"
    orphan.write_text("do not delete", encoding="utf-8")

    report = audit_attachment_storage(
        storage_root=root,
        records=[],
    )

    assert any(
        issue.category == "untracked_file"
        and issue.stored_name == "orphan.txt"
        for issue in report.issues
    )
    assert orphan.read_text(encoding="utf-8") == "do not delete"


def test_audit_flags_database_path_mismatch(
    tmp_path: Path,
) -> None:
    root = tmp_path / "uploads"
    user_dir = root / "user-a"
    user_dir.mkdir(parents=True)

    actual_file = user_dir / "actual.txt"
    actual_file.write_text("private", encoding="utf-8")

    wrong_recorded_path = user_dir / "different.txt"

    report = audit_attachment_storage(
        storage_root=root,
        records=[
            ("user-a", "actual.txt", wrong_recorded_path),
        ],
    )

    assert any(
        issue.category == "unsafe_path"
        for issue in report.issues
    )


def test_audit_does_not_delete_files(tmp_path: Path) -> None:
    root = tmp_path / "uploads"
    user_dir = root / "user-a"
    user_dir.mkdir(parents=True)

    orphan = user_dir / "keep.txt"
    orphan.write_text("must remain", encoding="utf-8")

    audit_attachment_storage(
        storage_root=root,
        records=[],
    )

    assert orphan.exists()
    assert orphan.read_text(encoding="utf-8") == "must remain"
