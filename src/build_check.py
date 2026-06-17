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
import time
from pathlib import Path

from src.logger import log

_DEFAULT_TIMEOUT_MINUTES = int(os.environ.get("BUILD_TIMEOUT_MINUTES", "20"))

# True only when both java and gradle are on PATH — absent in the alpine image
def _check_java_available() -> bool:
    try:
        ok = subprocess.run(["java", "-version"], capture_output=True).returncode == 0
        return ok and subprocess.run(["gradle", "--version"], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False

_JAVA_AVAILABLE = _check_java_available()

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


def verify(repo_root: Path, module: str, timeout_minutes: int | None = None) -> None:
    """Compile the flyway module in *repo_root* for *module*.

    In local dev: runs setup-local-gradle.sh if available to sync gradle.properties.
    In container: gradle.properties is already written by docker-entrypoint.sh.
    Raises BuildCheckError on compilation failure or timeout. Returns normally on success.

    timeout_minutes: kill Gradle after this many minutes. Defaults to BUILD_TIMEOUT_MINUTES
    env var (default 20). Pass 0 to disable.
    """
    gradle_path = _MODULE_GRADLE_PATH.get(module)
    if gradle_path is None:
        raise BuildCheckError(
            f"Unknown module '{module}' for build check. "
            f"Known modules: {list(_MODULE_GRADLE_PATH)}"
        )

    timeout_secs = (
        (timeout_minutes * 60) if timeout_minutes is not None else
        (_DEFAULT_TIMEOUT_MINUTES * 60 if _DEFAULT_TIMEOUT_MINUTES > 0 else None)
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

    cmd = [
        "gradle",
        f"{gradle_path}:compileJava",
        "-x", "test",
        "-Penv=dev",
        "-PcustomerOverlay=ecuador",
    ]

    if not _JAVA_AVAILABLE:
        log("BUILD", "java/gradle not available — skipping compile step")
        return

    log("BUILD", f"gradle {gradle_path}:compileJava — module={module}")
    t0 = time.monotonic()

    proc = subprocess.Popen(
        cmd,
        cwd=str(abs_repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )

    output_lines = []
    for line in proc.stdout:
        line = line.rstrip()
        output_lines.append(line)
        print(f"[gradle] {line}", flush=True)
        if timeout_secs and (time.monotonic() - t0) > timeout_secs:
            proc.kill()
            proc.stdout.close()
            proc.wait()
            raise BuildCheckError(
                f"Build timed out after {timeout_minutes or _DEFAULT_TIMEOUT_MINUTES} minutes "
                f"for module '{module}' — Gradle process killed"
            )

    proc.wait()
    elapsed = time.monotonic() - t0

    if proc.returncode != 0:
        output = "\n".join(output_lines).strip()
        raise BuildCheckError(
            f"Compilation failed for module '{module}':\n{output}"
        )

    log("BUILD", f"compilation OK — {module} ({elapsed:.1f}s)")
