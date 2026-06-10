"""Place generated files into the target repo and optionally commit."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_MODULE_JAVA_PATH = {
    "ams-rule": "ams-rule/flyway/src/main/java/eu/ncdc/arizona/rule/db/migration",
    "ams-policy": "ams-policy/flyway/src/main/java/eu/ncdc/arizona/policy/db/migration",
}
_MODULE_RESOURCES_PATH = {
    "ams-rule": "ams-rule/flyway/src/main/resources/db/migration",
    "ams-policy": "ams-policy/flyway/src/main/resources/db/migration",
}


def place(
    xlsx_src: Path,
    java_src: Path,
    base_name: str,
    module: str,
    repo_root: Path,
) -> tuple[Path, Path]:
    """
    Copy xlsx and java files into the correct paths inside *repo_root*.
    Returns (xlsx_dest, java_dest).
    """
    java_dir = repo_root / _MODULE_JAVA_PATH[module]
    res_dir = repo_root / _MODULE_RESOURCES_PATH[module]

    java_dir.mkdir(parents=True, exist_ok=True)
    res_dir.mkdir(parents=True, exist_ok=True)

    xlsx_dest = res_dir / f"{base_name}.xlsx"
    java_dest = java_dir / f"{base_name}.java"

    shutil.copy2(xlsx_src, xlsx_dest)
    shutil.copy2(java_src, java_dest)

    return xlsx_dest, java_dest


def create_feature_branch(repo_root: Path, branch_name: str, base_branch: str = "develop") -> None:
    """Create and checkout *branch_name* from *base_branch* in *repo_root*.

    Fetches the latest *base_branch* from origin before branching so the
    feature branch is always up-to-date with pre-production.
    """
    r = str(Path(repo_root).resolve())
    subprocess.run(["git", "-C", r, "fetch", "origin", base_branch], check=True)
    subprocess.run(
        ["git", "-C", r, "checkout", "-b", branch_name, f"origin/{base_branch}"],
        check=True,
    )
    print(f"  branch '{branch_name}' created from origin/{base_branch}")


def git_add_commit(repo_root: Path, files: list[Path], ticket_id: str, description: str) -> None:
    """Stage *files* and create a commit in *repo_root*."""
    abs_root = Path(repo_root).resolve()
    rel_files = [str(Path(f).resolve().relative_to(abs_root)) for f in files]
    subprocess.run(["git", "-C", str(abs_root), "add"] + rel_files, check=True)
    msg = f"[{ticket_id}] {description}"
    subprocess.run(["git", "-C", str(abs_root), "commit", "-m", msg], check=True)
