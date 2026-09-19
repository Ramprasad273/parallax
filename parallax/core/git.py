"""Safe Git interaction layer for Parallax."""

import fnmatch
import subprocess
from pathlib import Path

from parallax.core.logging import logger
from parallax.core.models import ChangedFile, FileChangeType


class GitError(Exception):
    """Raised when a Git command fails."""


class GitResolver:
    """Safely extracts changed SQL files between git references or the working tree."""

    def __init__(self, repo_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root or ".").resolve()
        try:
            top_level = self._run_git(["rev-parse", "--show-toplevel"]).strip()
            self.git_root = Path(top_level).resolve()
        except GitError:
            self.git_root = self.repo_root

    def _run_git(self, args: list[str]) -> str:
        """Run a git command safely without shell=True."""
        cmd = ["git"] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError as e:
            raise GitError("Git executable not found in PATH.") from e
        except Exception as e:
            raise GitError(f"Failed to execute git command: {e}") from e

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise GitError(f"Git command failed (exit code {result.returncode}): {stderr}")

        return result.stdout

    def is_git_repository(self) -> bool:
        """Check if repo_root is inside a valid git repository."""
        try:
            out = self._run_git(["rev-parse", "--is-inside-work-tree"]).strip()
            return out == "true"
        except GitError:
            return False

    def get_merge_base(self, base_ref: str, head_ref: str = "HEAD") -> str:
        """Get the merge-base commit between two refs."""
        out = self._run_git(["merge-base", base_ref, head_ref]).strip()
        return out

    def get_file_content_at_ref(self, file_path: str, ref: str) -> str | None:
        """Safely retrieve file content from a specific git ref (e.g. 'origin/main')."""
        normalized = Path(file_path).as_posix()
        try:
            return self._run_git(["show", f"{ref}:{normalized}"])
        except GitError:
            return None

    def get_changed_sql_files(
        self,
        base_ref: str = "origin/main",
        head_ref: str = "HEAD",
        include_working_tree: bool = True,
        ignore_patterns: list[str] | None = None,
    ) -> list[ChangedFile]:
        """
        Identify changed .sql files between base_ref and head_ref (or working tree).

        If include_working_tree is True and head_ref is HEAD, uncommitted staged and unstaged
        changes in the working tree are also inspected.
        """
        if not self.is_git_repository():
            raise GitError(f"Directory '{self.repo_root}' is not a Git repository.")

        ignore_patterns = ignore_patterns or []

        resolved_base = base_ref
        try:
            self._run_git(["rev-parse", "--verify", base_ref])
        except GitError:
            for fallback in ["main", "master", "HEAD"]:
                try:
                    self._run_git(["rev-parse", "--verify", fallback])
                    resolved_base = fallback
                    logger.warning(
                        "Base ref '%s' not found; falling back to '%s'.", base_ref, fallback
                    )
                    break
                except GitError:
                    continue

        diff_args = ["diff", "--name-status", "--no-renames", resolved_base]
        if not include_working_tree:
            diff_args = ["diff", "--name-status", "--no-renames", f"{resolved_base}...{head_ref}"]

        try:
            raw_diff = self._run_git(diff_args)
        except GitError:
            raw_diff = self._run_git(
                ["diff", "--name-status", "--no-renames", resolved_base, head_ref]
            )

        untracked_files: list[str] = []
        if include_working_tree:
            try:
                untracked_out = self._run_git(["ls-files", "--others", "--exclude-standard"])
                untracked_files = [f.strip() for f in untracked_out.splitlines() if f.strip()]
            except GitError:
                pass

        results: list[ChangedFile] = []
        seen_paths: set[str] = set()

        for line in raw_diff.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            status_code, path_str = parts[0].strip(), parts[1].strip()
            norm_path = Path(path_str).as_posix()

            if not norm_path.endswith(".sql"):
                continue

            if any(fnmatch.fnmatch(norm_path, pat) for pat in ignore_patterns):
                logger.debug(f"Ignoring file matching pattern: {norm_path}")
                continue

            if norm_path in seen_paths:
                continue
            seen_paths.add(norm_path)

            status_char = status_code[0].upper()
            if status_char == "A":
                change_type = FileChangeType.ADDED
                base_content = None
                head_content = self._get_current_or_ref_content(
                    norm_path, head_ref, include_working_tree
                )
            elif status_char == "D":
                change_type = FileChangeType.DELETED
                base_content = self.get_file_content_at_ref(norm_path, resolved_base)
                head_content = None
            else:
                change_type = FileChangeType.MODIFIED
                base_content = self.get_file_content_at_ref(norm_path, resolved_base)
                head_content = self._get_current_or_ref_content(
                    norm_path, head_ref, include_working_tree
                )

            results.append(
                ChangedFile(
                    path=norm_path,
                    change_type=change_type,
                    base_content=base_content,
                    head_content=head_content,
                )
            )

        for u_path in untracked_files:
            norm_path = Path(u_path).as_posix()
            if not norm_path.endswith(".sql") or norm_path in seen_paths:
                continue
            if any(fnmatch.fnmatch(norm_path, pat) for pat in ignore_patterns):
                continue
            seen_paths.add(norm_path)
            content = ""
            for root in (self.git_root, self.repo_root):
                full_path = root / norm_path
                if full_path.is_file():
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    break
            results.append(
                ChangedFile(
                    path=norm_path,
                    change_type=FileChangeType.ADDED,
                    base_content=None,
                    head_content=content,
                )
            )

        return results

    def _get_current_or_ref_content(
        self, path: str, ref: str, from_working_tree: bool
    ) -> str | None:
        if from_working_tree:
            for root in (self.git_root, self.repo_root):
                full_path = root / path
                if full_path.is_file():
                    return full_path.read_text(encoding="utf-8", errors="replace")
        return self.get_file_content_at_ref(path, ref)
