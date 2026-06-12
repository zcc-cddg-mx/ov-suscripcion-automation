"""Build verification step — compiles the generated Java class via Gradle.

Runs before git push to catch syntax/class errors early.
Does NOT generate JARs — full build is Azure DevOps pipeline responsibility.

Environment resolution (in order of priority):
  1. Container: gradle.properties already written by docker-entrypoint.sh
                from GRADLE_USERNAME / GRADLE_DEV_PASSWORD env vars.
                JAVA_HOME set by the eclipse-temurin base image.
  2. Local dev:  setup-local-gradle.sh (LOCAL_SETUP_SCRIPT) applies the same
                 config from the ov-zec-handover artifact. Only runs if the
                 script exists at the expected path.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# Maps Code Agent module names to Gradle subproject paths
_MODULE_GRADLE_PATH = {
    "ams-policy": ":ams-policy:flyway",
    "ams-rule":   ":ams-rule:flyway",
}

# Local dev only — skipped in container (entrypoint already wrote gradle.properties)
_LOCAL_SETUP_SCRIPT = Path(
    "/home/idavid/dev/ov/ov-zec-handover/ov-local-build/build-artifacts/gradle/setup-local-gradle.sh"
)

# Local dev JAVA_HOME — in container, eclipse-temurin sets JAVA_HOME automatically
_LOCAL_JAVA_HOME = Path("/usr/lib/jvm/temurin-8-jdk-amd64")


class BuildCheckError(Exception):
    pass


def verify(repo_root: Path, module: str) -> None:
    """Compile the flyway module in *repo_root* for *module*.

    In local dev: runs setup-local-gradle.sh if available to sync gradle.properties.
    In container: gradle.properties is already written by docker-entrypoint.sh.
    Raises BuildCheckError on compilation failure. Returns normally on success.
    """
    gradle_path = _MODULE_GRADLE_PATH.get(module)
    if gradle_path is None:
        raise BuildCheckError(
            f"Unknown module '{module}' for build check. "
            f"Known modules: {list(_MODULE_GRADLE_PATH)}"
        )

    abs_repo = Path(repo_root).resolve()

    # Local dev: apply Gradle config if setup script is available (idempotent)
    if _LOCAL_SETUP_SCRIPT.exists():
        result = subprocess.run(
            ["bash", str(_LOCAL_SETUP_SCRIPT)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise BuildCheckError(
                f"setup-local-gradle.sh failed:\n{result.stderr}"
            )

    # Build env: prefer JAVA_HOME from environment (container sets it via base image)
    java_home = os.environ.get("JAVA_HOME", str(_LOCAL_JAVA_HOME))
    env = {
        **os.environ,
        "JAVA_HOME": java_home,
        "PATH": f"{java_home}/bin:{os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}",
    }

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
