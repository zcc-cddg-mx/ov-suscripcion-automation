#!/usr/bin/env sh
# docker-entrypoint-lite.sh — entrypoint para ov-code-agent-lite (Alpine)
#
# Versión reducida de docker-entrypoint.sh: sin Java, sin Gradle, sin Maven.
# El repo backend se clona en primer arranque; en reinicios solo se actualiza.
#
# Required environment variables:
#   GIT_USERNAME  — Azure Repos username
#   GIT_PAT       — Azure Repos PAT (Code Read+Write)
#
# Optional:
#   REPO_PATH     — path donde clonar/actualizar el repo (default: /repos/ov-arizona-backend-ecuador)
#   PORT          — HTTP port (default: 5000)

set -eu

: "${GIT_USERNAME:?GIT_USERNAME is required}"
: "${GIT_PAT:?GIT_PAT is required}"

REPO_PATH="${REPO_PATH:-/repos/ov-arizona-backend-ecuador}"
PORT="${PORT:-5000}"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Generate /app/config.json
# ─────────────────────────────────────────────────────────────────────────────
cat > /app/config.json <<EOF
{
  "repo": "${REPO_PATH}"
}
EOF
echo "[entrypoint-lite] config.json → repo: ${REPO_PATH}"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Configure git credentials
# ─────────────────────────────────────────────────────────────────────────────
git config --global credential.helper store
printf "https://ZurichInsurance-EC:%s@dev.azure.com\n" "${GIT_PAT}" >> ~/.git-credentials
printf "https://%s:%s@dev.azure.com\n" "${GIT_USERNAME}" "${GIT_PAT}" >> ~/.git-credentials

git config --global user.email "${GIT_USERNAME}@zurichinsurance.com"
git config --global user.name  "${GIT_USERNAME}"

echo "[entrypoint-lite] git credentials configured"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Clone repo on first start; update branches on restart
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -d "${REPO_PATH}/.git" ]; then
    echo "[entrypoint-lite] cloning repo backend..."
    git clone \
        "https://ZurichInsurance-EC:${GIT_PAT}@dev.azure.com/ZurichInsurance-EC/Oficina-Virtual-ZEC/_git/ov-arizona-backend-ecuador" \
        "${REPO_PATH}"
    cd "${REPO_PATH}"
    for branch in main develop test developer; do
        git fetch origin "${branch}:${branch}" 2>/dev/null || true
    done
    git checkout developer
    echo "[entrypoint-lite] repo cloned OK"
else
    echo "[entrypoint-lite] updating repo branches..."
    git config --global --add safe.directory "${REPO_PATH}"
    cd "${REPO_PATH}"
    git fetch origin 2>&1 | sed 's/^/[entrypoint-lite] /' || true
    for branch in main develop test developer; do
        git fetch origin "${branch}:${branch}" 2>/dev/null && \
            echo "[entrypoint-lite] branch ${branch} updated" || \
            echo "[entrypoint-lite] branch ${branch} not found — skipping"
    done
    git checkout developer
fi

cd /app

# ─────────────────────────────────────────────────────────────────────────────
# 4. Start application
# ─────────────────────────────────────────────────────────────────────────────
echo "[entrypoint-lite] starting Code Agent (lite) on port ${PORT}"
export PORT
exec "$@"
