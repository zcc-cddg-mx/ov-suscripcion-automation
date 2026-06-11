"""Place generated files into the target repo and optionally commit and push.

Branch strategy:
  feature/{ticket}_{suffix}  →  PR →  developer  (integration/QA)
  developer                  →  PR →  main        (production — future, manual process)

The Code Agent only operates on the developer branch. Promotion to main/production
is a separate, manually-triggered step outside this agent's scope.
"""

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

_EXPECTED_FILES = 2       # exactly one .xlsx + one .java per migration
_PR_TARGET_BRANCH = "developer"  # PRs always target developer; main/production is a separate manual step


def place(
    xlsx_src: Path,
    java_src: Path,
    base_name: str,
    module: str,
    repo_root: Path,
) -> tuple[Path, Path]:
    """Copy xlsx and java files into the correct paths inside *repo_root*.

    Enforces the rule: exactly 2 files per migration (one .xlsx + one .java).
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

    # Invariant: exactly 2 files placed — fail loud if something went wrong
    placed = [xlsx_dest, java_dest]
    assert len(placed) == _EXPECTED_FILES, (
        f"Migration must produce exactly {_EXPECTED_FILES} files, got {len(placed)}"
    )

    return xlsx_dest, java_dest


def create_feature_branch(repo_root: Path, branch_name: str, base_branch: str = "developer") -> None:
    """Create and checkout *branch_name* from *base_branch* in *repo_root*.

    Base branch is 'developer' (integration/QA). Feature branches are always
    cut from developer — never from main/production.
    """
    r = str(Path(repo_root).resolve())
    subprocess.run(["git", "-C", r, "fetch", "origin", base_branch], check=True)
    subprocess.run(
        ["git", "-C", r, "checkout", "-b", branch_name, f"origin/{base_branch}"],
        check=True,
    )
    print(f"  branch '{branch_name}' created from origin/{base_branch}")


def _validate_migration_pair(files: list[Path]) -> None:
    """Raise if *files* is not exactly one .xlsx + one .java with matching stems."""
    if len(files) != _EXPECTED_FILES:
        raise ValueError(
            f"Expected exactly {_EXPECTED_FILES} files per migration commit "
            f"(one .xlsx + one .java), got {len(files)}: {[f.name for f in files]}"
        )
    xlsx = next((f for f in files if f.suffix == ".xlsx"), None)
    java = next((f for f in files if f.suffix == ".java"), None)
    if xlsx is None or java is None:
        found = [f.suffix for f in files]
        raise ValueError(
            f"Migration pair must be one .xlsx + one .java, got: {found}"
        )
    if xlsx.stem != java.stem:
        raise ValueError(
            f"Migration file names must match: {xlsx.name!r} vs {java.name!r}"
        )
    # Verify the Java class name inside the file matches the file stem
    java_content = java.read_text(encoding="utf-8")
    if f"class {java.stem}" not in java_content:
        raise ValueError(
            f"Java class name does not match file name {java.stem!r}. "
            f"Expected 'class {java.stem}' inside {java.name!r}"
        )


def git_add_commit_push(
    repo_root: Path,
    files: list[Path],
    ticket_id: str,
    description: str,
    branch_name: str,
) -> None:
    """Stage *files*, commit, and push *branch_name* to origin.

    Enforces exactly 2 files per commit (one .xlsx + one .java with matching names).
    """
    _validate_migration_pair(files)

    abs_root = Path(repo_root).resolve()
    rel_files = [str(Path(f).resolve().relative_to(abs_root)) for f in files]

    subprocess.run(["git", "-C", str(abs_root), "add"] + rel_files, check=True)
    msg = f"[{ticket_id}] {description}"
    subprocess.run(["git", "-C", str(abs_root), "commit", "-m", msg], check=True)
    subprocess.run(
        ["git", "-C", str(abs_root), "push", "--set-upstream", "origin", branch_name],
        check=True,
    )
    print(f"  pushed '{branch_name}' to origin")


# Keep old name as alias for backward compatibility with tests
def git_add_commit(repo_root: Path, files: list[Path], ticket_id: str, description: str) -> None:
    """Stage *files* and create a commit (no push). Used in tests."""
    abs_root = Path(repo_root).resolve()
    rel_files = [str(Path(f).resolve().relative_to(abs_root)) for f in files]
    subprocess.run(["git", "-C", str(abs_root), "add"] + rel_files, check=True)
    msg = f"[{ticket_id}] {description}"
    subprocess.run(["git", "-C", str(abs_root), "commit", "-m", msg], check=True)
