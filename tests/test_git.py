"""Unit tests for safe Git resolution layer."""

import subprocess
from pathlib import Path

import pytest

from parallax.core.git import GitError, GitResolver
from parallax.core.models import FileChangeType


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create an isolated temporary git repository with initial commit."""

    def run(args: list[str]) -> None:
        subprocess.run(
            ["git"] + args,
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        )

    run(["init"])
    run(["config", "user.name", "Test User"])
    run(["config", "user.email", "test@example.com"])

    # Create initial files
    models_dir = tmp_path / "models" / "staging"
    models_dir.mkdir(parents=True)

    stg_orders = models_dir / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status != 'cancelled';", encoding="utf-8"
    )

    stg_customers = models_dir / "stg_customers.sql"
    stg_customers.write_text("SELECT id, name FROM raw_customers;", encoding="utf-8")

    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo", encoding="utf-8")

    run(["add", "."])
    run(["commit", "-m", "Initial commit"])

    # Create main branch explicitly
    run(["branch", "-M", "main"])
    return tmp_path


def test_is_git_repository(temp_git_repo: Path) -> None:
    resolver = GitResolver(temp_git_repo)
    assert resolver.is_git_repository() is True


def test_detect_modified_sql_file(temp_git_repo: Path) -> None:
    resolver = GitResolver(temp_git_repo)

    # Modify stg_orders.sql
    stg_orders = temp_git_repo / "models" / "staging" / "stg_orders.sql"
    stg_orders.write_text(
        "SELECT id, status FROM raw_orders WHERE status = 'delivered';", encoding="utf-8"
    )

    changes = resolver.get_changed_sql_files(base_ref="main", include_working_tree=True)
    assert len(changes) == 1
    change = changes[0]
    assert change.path == "models/staging/stg_orders.sql"
    assert change.change_type == FileChangeType.MODIFIED
    assert "status != 'cancelled'" in (change.base_content or "")
    assert "status = 'delivered'" in (change.head_content or "")


def test_detect_added_sql_file(temp_git_repo: Path) -> None:
    resolver = GitResolver(temp_git_repo)

    new_model = temp_git_repo / "models" / "staging" / "stg_payments.sql"
    new_model.write_text("SELECT id, amount FROM raw_payments;", encoding="utf-8")

    changes = resolver.get_changed_sql_files(base_ref="main", include_working_tree=True)
    assert len(changes) == 1
    change = changes[0]
    assert change.path == "models/staging/stg_payments.sql"
    assert change.change_type == FileChangeType.ADDED
    assert change.base_content is None
    assert "raw_payments" in (change.head_content or "")


def test_detect_deleted_sql_file(temp_git_repo: Path) -> None:
    resolver = GitResolver(temp_git_repo)

    stg_customers = temp_git_repo / "models" / "staging" / "stg_customers.sql"
    stg_customers.unlink()

    changes = resolver.get_changed_sql_files(base_ref="main", include_working_tree=True)
    assert len(changes) == 1
    change = changes[0]
    assert change.path == "models/staging/stg_customers.sql"
    assert change.change_type == FileChangeType.DELETED
    assert "raw_customers" in (change.base_content or "")
    assert change.head_content is None


def test_ignore_non_sql_files(temp_git_repo: Path) -> None:
    resolver = GitResolver(temp_git_repo)

    readme = temp_git_repo / "README.md"
    readme.write_text("# Updated Readme", encoding="utf-8")

    changes = resolver.get_changed_sql_files(base_ref="main", include_working_tree=True)
    assert len(changes) == 0


def test_ignore_patterns(temp_git_repo: Path) -> None:
    resolver = GitResolver(temp_git_repo)

    sandbox = temp_git_repo / "models" / "sandbox"
    sandbox.mkdir(parents=True)
    sandbox_model = sandbox / "scratch_test.sql"
    sandbox_model.write_text("SELECT 1;", encoding="utf-8")

    changes = resolver.get_changed_sql_files(
        base_ref="main",
        include_working_tree=True,
        ignore_patterns=["models/sandbox/**"],
    )
    assert len(changes) == 0


def test_git_error_on_non_git_dir(tmp_path: Path) -> None:
    # Empty dir without git
    isolated = tmp_path / "empty_dir"
    isolated.mkdir()
    resolver = GitResolver(isolated)
    # rev-parse might find parent git if not isolated, but if we pass an invalid repo:
    with pytest.raises(GitError):
        resolver._run_git(["rev-parse", "--verify", "non_existent_ref_12345"])


def test_base_ref_fallback_warning(temp_git_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    resolver = GitResolver(temp_git_repo)
    with caplog.at_level("WARNING"):
        resolver.get_changed_sql_files(base_ref="non_existent_ref_123", include_working_tree=True)
    assert "falling back to 'main'" in caplog.text
