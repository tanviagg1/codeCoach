"""
git_tools — utilities for extracting git information about a file.

These are pure functions that wrap GitPython.
Used to enrich the code context with git metadata before review.

Requires: gitpython (in requirements.txt)
"""

from pathlib import Path


def get_git_diff(filepath: str, repo_path: str = ".") -> str:
    """
    Get the git diff for a specific file (staged or unstaged changes).

    Args:
        filepath: Path to the file to diff
        repo_path: Path to the git repository root

    Returns:
        The diff string, or an empty string if no diff or not a git repo
    """
    try:
        import git
        repo = git.Repo(repo_path, search_parent_directories=True)
        # Try staged diff first, then unstaged
        diff = repo.git.diff("--cached", filepath)
        if not diff:
            diff = repo.git.diff(filepath)
        return diff
    except Exception:
        return ""


def get_file_history_summary(filepath: str, repo_path: str = ".", max_commits: int = 5) -> str:
    """
    Get a brief commit history for a file.

    Args:
        filepath: Path to the file
        repo_path: Path to the git repository root
        max_commits: How many recent commits to include

    Returns:
        A formatted string of recent commits for this file
    """
    try:
        import git
        repo = git.Repo(repo_path, search_parent_directories=True)
        commits = list(repo.iter_commits(paths=filepath, max_count=max_commits))
        if not commits:
            return "No git history found for this file."
        lines = [f"- {c.hexsha[:7]} | {c.author.name} | {c.committed_datetime.date()} | {c.message.strip()}"
                 for c in commits]
        return "\n".join(lines)
    except Exception:
        return "Could not read git history."


def get_blame_summary(filepath: str, repo_path: str = ".") -> dict:
    """
    Return a summary of who wrote which parts of the file.

    Args:
        filepath: Path to the file
        repo_path: Git repo root

    Returns:
        Dict mapping author name → number of lines authored
    """
    try:
        import git
        repo = git.Repo(repo_path, search_parent_directories=True)
        blame = repo.blame("HEAD", filepath)
        author_counts: dict[str, int] = {}
        for commit, lines in blame:
            author = commit.author.name
            author_counts[author] = author_counts.get(author, 0) + len(lines)
        return author_counts
    except Exception:
        return {}


def read_file(filepath: str) -> str:
    """
    Read a source file from disk.

    Args:
        filepath: Absolute or relative path to the file

    Returns:
        File contents as a string

    Raises:
        FileNotFoundError: if the file does not exist
        ValueError: if the file is empty
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"File is empty: {filepath}")
    return content
