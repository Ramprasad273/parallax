"""Unit tests for GitHub Action PR comment bot and step summary."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from parallax.github.action import GitHubActionRunner, run_action


def test_get_pr_metadata_from_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    event_file = tmp_path / "event.json"
    event_data = {
        "repository": {"full_name": "acme/data-models"},
        "pull_request": {"number": 42},
    }
    event_file.write_text(json.dumps(event_data), encoding="utf-8")

    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))

    runner = GitHubActionRunner(token="test-token")
    repo, pr_num = runner.get_pr_metadata()
    assert repo == "acme/data-models"
    assert pr_num == 42


def test_get_pr_metadata_from_env_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/data-models")
    monkeypatch.setenv("PR_NUMBER", "101")

    runner = GitHubActionRunner(token="test-token")
    repo, pr_num = runner.get_pr_metadata()
    assert repo == "acme/data-models"
    assert pr_num == 101


def test_write_step_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    summary_file = tmp_path / "step_summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    runner = GitHubActionRunner(token="test-token")
    runner.write_step_summary("### Parallax Report Passed")

    assert summary_file.is_file()
    assert "Parallax Report Passed" in summary_file.read_text(encoding="utf-8")


def test_post_new_comment_when_none_exists() -> None:
    runner = GitHubActionRunner(token="secret-token")

    # Mock urllib responses:
    # 1. GET returns empty comments list []
    # 2. POST returns 201 Created
    get_resp = MagicMock()
    get_resp.read.return_value = b"[]"
    get_resp.__enter__.return_value = get_resp

    post_resp = MagicMock()
    post_resp.status = 201
    post_resp.__enter__.return_value = post_resp

    with patch("urllib.request.urlopen", side_effect=[get_resp, post_resp]) as mock_urlopen:
        success = runner.post_or_update_pr_comment(
            "acme/repo", 42, "<!-- parallax-ci-comment -->\nHello"
        )
        assert success is True
        assert mock_urlopen.call_count == 2
        # Verify POST request was made
        post_call = mock_urlopen.call_args_list[1][0][0]
        assert post_call.method == "POST"
        assert "/issues/42/comments" in post_call.full_url


def test_update_existing_comment_in_place() -> None:
    runner = GitHubActionRunner(token="secret-token")

    # Mock urllib responses:
    # 1. GET returns existing comment with marker
    existing_comments = [{"id": 9999, "body": "<!-- parallax-ci-comment -->\nOld report"}]
    get_resp = MagicMock()
    get_resp.read.return_value = json.dumps(existing_comments).encode("utf-8")
    get_resp.__enter__.return_value = get_resp

    # 2. PATCH returns 200 OK
    patch_resp = MagicMock()
    patch_resp.status = 200
    patch_resp.__enter__.return_value = patch_resp

    with patch("urllib.request.urlopen", side_effect=[get_resp, patch_resp]) as mock_urlopen:
        success = runner.post_or_update_pr_comment(
            "acme/repo", 42, "<!-- parallax-ci-comment -->\nNew report"
        )
        assert success is True
        assert mock_urlopen.call_count == 2
        # Verify PATCH request was made to /issues/comments/9999
        patch_call = mock_urlopen.call_args_list[1][0][0]
        assert patch_call.method == "PATCH"
        assert "/issues/comments/9999" in patch_call.full_url


def test_run_action_no_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setattr(
        "parallax.core.git.GitResolver.get_changed_sql_files", lambda *args, **kwargs: []
    )
    with pytest.raises(SystemExit) as exc:
        run_action()
    assert exc.value.code == 0


def test_run_action_with_changes_and_comment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from parallax.core.models import ChangedFile, FileChangeType

    cf = ChangedFile(
        path="models/staging/stg_orders.sql",
        change_type=FileChangeType.MODIFIED,
        base_content="SELECT id, status FROM raw_orders WHERE status != 'cancelled';",
        head_content="SELECT id, status FROM raw_orders WHERE status = 'delivered';",
    )
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setattr(
        "parallax.core.git.GitResolver.get_changed_sql_files", lambda *args, **kwargs: [cf]
    )
    monkeypatch.setenv("INPUT_FAIL_ON", "NEVER")
    monkeypatch.setenv("INPUT_MANIFEST", str(tmp_path / "non_existent.json"))
    monkeypatch.setenv("GITHUB_REPOSITORY", "acme/repo")
    monkeypatch.setenv("PR_NUMBER", "42")
    monkeypatch.setattr(
        "parallax.github.action.GitHubActionRunner.post_or_update_pr_comment", lambda *args: True
    )

    with pytest.raises(SystemExit) as exc:
        run_action()
    assert exc.value.code == 0
