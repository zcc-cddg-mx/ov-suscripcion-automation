#!/usr/bin/env sh
# docker-entrypoint.sh — entrypoint para ov-code-agent (Alpine)
#
# Sin Java, sin Gradle, sin Maven.
# El repo backend se clona en primer arranque; en reinicios solo git pull.
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
echo "[entrypoint] config.json → repo: ${REPO_PATH}"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Configure git credentials
# ─────────────────────────────────────────────────────────────────────────────
git config --global credential.helper store
printf "https://ZurichInsurance-EC:%s@dev.azure.com\n" "${GIT_PAT}" >> ~/.git-credentials
printf "https://%s:%s@dev.azure.com\n" "${GIT_USERNAME}" "${GIT_PAT}" >> ~/.git-credentials

git config --global user.email "${GIT_USERNAME}@zurichinsurance.com"
git config --global user.name  "${GIT_USERNAME}"

echo "[entrypoint] git credentials configured"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Clone repo on first start; git pull on restart
# ─────────────────────────────────────────────────────────────────────────────
git config --global --add safe.directory "${REPO_PATH}"

if [ ! -d "${REPO_PATH}/.git" ]; then
    echo "[entrypoint] first start — cloning repo backend..."
    git clone \
        "https://ZurichInsurance-EC:${GIT_PAT}@dev.azure.com/ZurichInsurance-EC/Oficina-Virtual-ZEC/_git/ov-arizona-backend-ecuador" \
        "${REPO_PATH}"
    cd "${REPO_PATH}"
    git checkout developer
    echo "[entrypoint] repo cloned OK — branch: developer"
else
    echo "[entrypoint] repo already present — pulling latest developer..."
    cd "${REPO_PATH}"
    git checkout developer
    git pull origin developer 2>&1 | sed 's/^/[entrypoint] /'
fi

cd /app

# ─────────────────────────────────────────────────────────────────────────────
# 4. Start application
# ─────────────────────────────────────────────────────────────────────────────
echo "[entrypoint] starting Code Agent (lite) on port ${PORT}"
export PORT
exec "$@"
