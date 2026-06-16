#!/usr/bin/env bash
# setup-local-gradle.sh
# Aplica el bloque local-repo al proyecto ov-arizona-backend-ecuador.
#
# Debe ejecutarse:
#   1. Una vez después de git clone (Dockerfile.base)
#   2. Después de cada git checkout de rama nueva (docker-entrypoint.sh)
#
# Idempotente: si el bloque ya existe no lo vuelve a insertar.

set -euo pipefail

BACKEND_DIR="${BACKEND_DIR:-/repos/ov-arizona-backend-ecuador}"
LOCAL_REPO_PATH="${BACKEND_DIR}/.project/local-repo"
BLOCK_MARKER="inicia bloque de compilacion local"

info()    { echo "[setup-gradle] $1"; }
success() { echo "[setup-gradle] OK — $1"; }
fail()    { echo "[setup-gradle] ERROR — $1" >&2; exit 1; }

[[ -d "$BACKEND_DIR" ]] || fail "directorio backend no encontrado: $BACKEND_DIR"

# ─────────────────────────────────────────────
# 1. gradle.properties — copia al root del proyecto
# ─────────────────────────────────────────────
TEMPLATE_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "${TEMPLATE_DIR}/gradle.properties" "${BACKEND_DIR}/gradle.properties"
success "gradle.properties copiado"

# ─────────────────────────────────────────────
# 2. build.gradle — inserta bloque local-repo
#    Ancla: primer mavenLocal() (buildscript.repositories)
#    Indentación: 8 espacios
# ─────────────────────────────────────────────
BUILD_FILE="${BACKEND_DIR}/build.gradle"

if grep -q "$BLOCK_MARKER" "$BUILD_FILE"; then
    info "build.gradle — bloque ya presente, omitiendo"
else
    python3 - "$BUILD_FILE" "$LOCAL_REPO_PATH" <<'PYEOF'
import sys

target, local_repo = sys.argv[1], sys.argv[2]
with open(target, 'r') as f:
    lines = f.readlines()

block = (
    "        // inicia bloque de compilacion local\n"
    f"        maven {{\n"
    f"            url uri(\"{local_repo}/\")\n"
    "            }\n"
    "        // termina bloque de compilacion local\n"
)

inserted = False
result = []
for line in lines:
    if not inserted and line.strip() == 'mavenLocal()':
        result.append(block)
        inserted = True
    result.append(line)

if not inserted:
    print("ERROR: no se encontró mavenLocal() en build.gradle", file=sys.stderr)
    sys.exit(1)

with open(target, 'w') as f:
    f.writelines(result)

print(f"  inserción OK")
PYEOF
    success "build.gradle actualizado"
fi

# ─────────────────────────────────────────────
# 3. dependencies.gradle — inserta bloque local-repo
#    Ancla: primer mavenLocal() (repositories raíz)
#    Indentación: 4 espacios
# ─────────────────────────────────────────────
DEPS_FILE="${BACKEND_DIR}/dependencies.gradle"

if grep -q "$BLOCK_MARKER" "$DEPS_FILE"; then
    info "dependencies.gradle — bloque ya presente, omitiendo"
else
    python3 - "$DEPS_FILE" "$LOCAL_REPO_PATH" <<'PYEOF'
import sys

target, local_repo = sys.argv[1], sys.argv[2]
with open(target, 'r') as f:
    lines = f.readlines()

block = (
    "    // inicia bloque de compilacion local\n"
    f"    maven {{\n"
    f"        url uri(\"{local_repo}/\")\n"
    "        }\n"
    "    // termina bloque de compilacion local\n"
)

inserted = False
result = []
for line in lines:
    if not inserted and line.strip() == 'mavenLocal()':
        result.append(block)
        inserted = True
    result.append(line)

if not inserted:
    print("ERROR: no se encontró mavenLocal() en dependencies.gradle", file=sys.stderr)
    sys.exit(1)

with open(target, 'w') as f:
    f.writelines(result)

print(f"  inserción OK")
PYEOF
    success "dependencies.gradle actualizado"
fi

success "setup completado — local-repo: ${LOCAL_REPO_PATH}"
