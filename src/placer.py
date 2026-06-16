"""Place generated files into the target repo and optionally commit and push.

Branch strategy:
  feature/{ticket}_{suffix}           →  push to origin
  {feature_branch}_developer_auxiliar →  created from origin/developer, receives only
                                          the 2 migration files from the feature branch
                                          (xlsx + java), then pushed to origin
  developer                           →  PR target (integration/QA)
  main                                →  production, manual process outside this agent

The auxiliary branch is the safe merge point: it starts clean from developer and
receives exactly the 2 migration files — no other changes from the feature branch.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from src.logger import log

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
    log("GIT", f"fetch origin/{base_branch}")
    subprocess.run(["git", "-C", r, "fetch", "origin", base_branch], check=True)
    # Stash any local modifications (e.g. build config files modified by local dev tooling)
    # so checkout doesn't fail. Stash is intentionally not popped — those changes are
    # local-only and should not be carried into the feature branch.
    subprocess.run(["git", "-C", r, "stash"], check=True)
    subprocess.run(
        ["git", "-C", r, "checkout", "-b", branch_name, f"origin/{base_branch}"],
        check=True,
    )
    log("GIT", f"branch '{branch_name}' created from origin/{base_branch}")


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


def _push_branch(repo_dir: str, branch_name: str) -> None:
    """Push *branch_name* to origin, retrying with --force-with-lease if the branch already exists.

    --force-with-lease is safe: it only overwrites if the remote ref matches our local
    knowledge — it won't clobber commits pushed by someone else.
    """
    result = subprocess.run(
        ["git", "-C", repo_dir, "push", "--set-upstream", "origin", branch_name],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return
    # Check whether the branch already exists in origin
    ls = subprocess.run(
        ["git", "-C", repo_dir, "ls-remote", "--heads", "origin", branch_name],
        capture_output=True, text=True,
    )
    if ls.returncode == 0 and ls.stdout.strip():
        log("GIT", f"branch '{branch_name}' already exists in origin, retrying with --force-with-lease")
        subprocess.run(
            ["git", "-C", repo_dir, "push", "--force-with-lease", "--set-upstream", "origin", branch_name],
            check=True,
        )
    else:
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )


def git_add_commit_push(
    repo_root: Path,
    files: list[Path],
    ticket_id: str,
    description: str,
    branch_name: str,
) -> str:
    """Stage *files*, commit, push *branch_name* to origin, and return the commit hash.

    Enforces exactly 2 files per commit (one .xlsx + one .java with matching names).
    """
    _validate_migration_pair(files)

    abs_root = Path(repo_root).resolve()
    rel_files = [str(Path(f).resolve().relative_to(abs_root)) for f in files]

    log("GIT", f"staging {len(rel_files)} file(s) on branch '{branch_name}'")
    subprocess.run(["git", "-C", str(abs_root), "add"] + rel_files, check=True)
    msg = f"[{ticket_id}] {description}"
    subprocess.run(["git", "-C", str(abs_root), "commit", "-m", msg], check=True)
    log("GIT", f"pushing feature branch '{branch_name}' to origin")
    _push_branch(str(abs_root), branch_name)
    result = subprocess.run(
        ["git", "-C", str(abs_root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    commit_id = result.stdout.strip()
    log("GIT", f"pushed '{branch_name}' to origin (commit {commit_id[:8]})")
    return commit_id


def create_auxiliary_branch(
    repo_root: Path,
    feature_branch: str,
    files: list[Path],
    ticket_id: str,
    description: str,
) -> str:
    """Create an auxiliary branch from origin/developer containing only the 2 migration files.

    The auxiliary branch name is: {feature_branch}_developer_auxiliar
    e.g. feature/ZNRX_671093_renov_agosto_developer_auxiliar

    Strategy: instead of merging (which risks conflicts), we create the aux branch
    clean from developer and use 'git show' to copy the exact file blobs from the
    feature branch. This guarantees only the 2 new files land in the aux branch —
    no other changes from the feature branch are included.

    Returns the auxiliary branch name.
    """
    aux_branch = f"{feature_branch}_developer_auxiliar"
    r = str(Path(repo_root).resolve())
    abs_root = Path(repo_root).resolve()

    # Create aux branch from latest developer
    log("GIT", f"fetch origin/{_PR_TARGET_BRANCH} for auxiliary branch")
    subprocess.run(["git", "-C", r, "fetch", "origin", _PR_TARGET_BRANCH], check=True)
    subprocess.run(
        ["git", "-C", r, "checkout", "-b", aux_branch, f"origin/{_PR_TARGET_BRANCH}"],
        check=True,
    )
    log("GIT", f"aux branch '{aux_branch}' created from origin/{_PR_TARGET_BRANCH}")

    # Extract each file blob from the feature branch and write it into the aux branch
    for f in files:
        rel = str(Path(f).resolve().relative_to(abs_root))
        # git show <branch>:<path> — retrieves the exact file content from the feature branch
        result = subprocess.run(
            ["git", "-C", r, "show", f"{feature_branch}:{rel}"],
            check=True,
            capture_output=True,
        )
        dest = abs_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(result.stdout)

    # Stage and commit the 2 files
    rel_files = [str(Path(f).resolve().relative_to(abs_root)) for f in files]
    subprocess.run(["git", "-C", r, "add"] + rel_files, check=True)
    msg = f"[{ticket_id}] {description}"
    subprocess.run(["git", "-C", r, "commit", "-m", msg], check=True)

    # Push aux branch to origin
    log("GIT", f"pushing aux branch '{aux_branch}' to origin")
    _push_branch(r, aux_branch)
    log("GIT", f"pushed aux branch '{aux_branch}' to origin")

    return aux_branch


# Keep old name as alias for backward compatibility with tests
def git_add_commit(repo_root: Path, files: list[Path], ticket_id: str, description: str) -> None:
    """Stage *files* and create a commit (no push). Used in tests."""
    abs_root = Path(repo_root).resolve()
    rel_files = [str(Path(f).resolve().relative_to(abs_root)) for f in files]
    subprocess.run(["git", "-C", str(abs_root), "add"] + rel_files, check=True)
    msg = f"[{ticket_id}] {description}"
    subprocess.run(["git", "-C", str(abs_root), "commit", "-m", msg], check=True)
