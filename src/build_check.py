"""Build verification step — compiles the generated Java class via Gradle.

Runs before git push to catch syntax/class errors early.
Does NOT generate JARs — full build is Azure DevOps pipeline responsibility.

Flow:
  1. setup-local-gradle.sh   — configures gradle.properties (credentials, local-repo)
  2. gradle :{module}:flyway:compileJava -x test -Penv=dev -PcustomerOverlay=ecuador
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Maps Code Agent module names to Gradle subproject paths
_MODULE_GRADLE_PATH = {
    "ams-policy": ":ams-policy:flyway",
    "ams-rule":   ":ams-rule:flyway",
}

_SETUP_SCRIPT = Path("/home/idavid/dev/ov/ov-zec-handover/ov-local-build/build-artifacts/gradle/setup-local-gradle.sh")
_JAVA_HOME = Path("/usr/lib/jvm/temurin-8-jdk-amd64")


class BuildCheckError(Exception):
    pass


def verify(repo_root: Path, module: str) -> None:
    """Compile the flyway module in *repo_root* for *module*.

    Runs setup-local-gradle.sh first to ensure gradle.properties is current,
    then compiles. Raises BuildCheckError with the Gradle output if compilation
    fails. Returns normally on success.
    """
    gradle_path = _MODULE_GRADLE_PATH.get(module)
    if gradle_path is None:
        raise BuildCheckError(
            f"Unknown module '{module}' for build check. "
            f"Known modules: {list(_MODULE_GRADLE_PATH)}"
        )

    abs_repo = Path(repo_root).resolve()

    # Step 1: apply local Gradle configuration (idempotent)
    if _SETUP_SCRIPT.exists():
        result = subprocess.run(
            ["bash", str(_SETUP_SCRIPT)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise BuildCheckError(
                f"setup-local-gradle.sh failed:\n{result.stderr}"
            )

    # Step 2: compile only — no tests, no JARs
    env = {"JAVA_HOME": str(_JAVA_HOME), "PATH": f"{_JAVA_HOME}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"}
    result = subprocess.run(
        [
            "gradle",
            f"{gradle_path}:compileJava",
            "-x", "test",
            "-Penv=dev",
            "-PcustomerOverlay=ecuador",
            "--quiet",
        ],
        cwd=str(abs_repo),
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        raise BuildCheckError(
            f"Compilation failed for module '{module}':\n{output}"
        )
