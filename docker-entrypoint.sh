#!/usr/bin/env bash
# docker-entrypoint.sh
#
# Generates runtime configuration from environment variables before starting the app.
#
# Required environment variables:
#   GRADLE_USERNAME      — Azure Artifacts username (e.g. carlos.duarte2)
#   GRADLE_DEV_PASSWORD  — Azure Artifacts PAT for dev feed
#   GIT_USERNAME         — Azure Repos username
#   GIT_PAT              — Azure Repos PAT (needs Code Read+Write)
#
# Optional:
#   REPO_PATH            — path to ov-arizona-backend-ecuador (default: /repos/ov-arizona-backend-ecuador)
#   PORT                 — HTTP port (default: 5000)
#   GRADLE_TEST_PASSWORD — Azure Artifacts PAT for test feed (defaults to GRADLE_DEV_PASSWORD)
#   GRADLE_PROD_PASSWORD — Azure Artifacts PAT for prod feed (defaults to GRADLE_DEV_PASSWORD)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Validate required vars
# ─────────────────────────────────────────────────────────────────────────────
: "${GRADLE_USERNAME:?GRADLE_USERNAME is required}"
: "${GRADLE_DEV_PASSWORD:?GRADLE_DEV_PASSWORD is required}"
: "${GIT_USERNAME:?GIT_USERNAME is required}"
: "${GIT_PAT:?GIT_PAT is required}"

REPO_PATH="${REPO_PATH:-/repos/ov-arizona-backend-ecuador}"
PORT="${PORT:-5000}"
GRADLE_TEST_PASSWORD="${GRADLE_TEST_PASSWORD:-$GRADLE_DEV_PASSWORD}"
GRADLE_PROD_PASSWORD="${GRADLE_PROD_PASSWORD:-$GRADLE_DEV_PASSWORD}"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Generate config.json (repo path for Code Agent)
# ─────────────────────────────────────────────────────────────────────────────
cat > /app/config.json <<EOF
{
  "repo": "${REPO_PATH}"
}
EOF

echo "[entrypoint] config.json → repo: ${REPO_PATH}"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Generate ~/.gradle/gradle.properties (Gradle credentials + env)
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p ~/.gradle

cat > ~/.gradle/gradle.properties <<EOF
org.gradle.daemon=true
org.gradle.parallel=true
org.gradle.jvmargs=-Xmx2048m -XX:+HeapDumpOnOutOfMemoryError -Dfile.encoding=UTF-8
org.gradle.workers.max=4
org.gradle.caching=true

env=dev
customerOverlay=ecuador

zurich-library-devUsername=${GRADLE_USERNAME}
zurich-library-devPassword=${GRADLE_DEV_PASSWORD}
zurich-library-devFeedUrl=https://pkgs.dev.azure.com/ZurichInsurance-EC/_packaging/zurich-library-dev/maven/v1

zurich-library-testUsername=${GRADLE_USERNAME}
zurich-library-testPassword=${GRADLE_TEST_PASSWORD}
zurich-library-testFeedUrl=https://pkgs.dev.azure.com/ZurichInsurance-EC/_packaging/zurich-library-uat/maven/v1

zurich-library-prodUsername=${GRADLE_USERNAME}
zurich-library-prodPassword=${GRADLE_PROD_PASSWORD}
zurich-library-prodFeedUrl=https://pkgs.dev.azure.com/ZurichInsurance-EC/_packaging/zurich-library-prod/maven/v1

systemProphttps.protocols=TLSv1.2,TLSv1.3
EOF

echo "[entrypoint] ~/.gradle/gradle.properties generated"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Configure git credentials for Azure Repos (PAT-based HTTPS)
# Azure Repos remotes use the org name (ZurichInsurance-EC) as the URL user,
# not the personal username — both entries are written so git credential lookup
# matches regardless of how the remote URL is configured.
# ─────────────────────────────────────────────────────────────────────────────
git config --global credential.helper store
printf "https://ZurichInsurance-EC:%s@dev.azure.com\n" "${GIT_PAT}" >> ~/.git-credentials
printf "https://%s:%s@dev.azure.com\n" "${GIT_USERNAME}" "${GIT_PAT}" >> ~/.git-credentials

git config --global user.email "${GIT_USERNAME}@zurichinsurance.com"
git config --global user.name  "${GIT_USERNAME}"

# Allow git to operate on the mounted repo (owned by host user, not container root)
git config --global --add safe.directory "${REPO_PATH}"

echo "[entrypoint] git credentials configured"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Verify repo is mounted
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -d "${REPO_PATH}/.git" ]; then
    echo "[entrypoint] WARNING: repo not found at ${REPO_PATH} — mount it with -v"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 5. Gradle warm-up — compile both modules once to:
#    a) download dependencies from Azure Artifacts into the cache volume
#    b) start the Gradle daemon so subsequent compiles reuse the warm JVM
#    Skipped if the repo is not mounted (dev/test without -v)
# ─────────────────────────────────────────────────────────────────────────────
if [ -d "${REPO_PATH}/.git" ]; then
    echo "[entrypoint] warming up Gradle daemon (first run may take a few minutes)..."
    for MODULE in ":ams-policy:flyway" ":ams-rule:flyway"; do
        gradle "${MODULE}:compileJava" -x test -Penv=dev -PcustomerOverlay=ecuador --quiet \
            -p "${REPO_PATH}" \
            && echo "[entrypoint] warm-up OK — ${MODULE}" \
            || echo "[entrypoint] WARN: warm-up failed for ${MODULE} (continuing)"
    done
fi

# ─────────────────────────────────────────────────────────────────────────────
# 6. Start application
# ─────────────────────────────────────────────────────────────────────────────
echo "[entrypoint] starting Code Agent on port ${PORT}"
export PORT
exec "$@"
