#!/usr/bin/env bash
# =============================================================================
# create_aux_branches.sh
#
# Creates auxiliary branches from origin/developer AND origin/test, copies
# exactly the migration files introduced by a feature branch (xlsx + java),
# commits, and pushes both aux branches to origin.
#
# Strategy: uses 'git show <feature>:<path>' instead of merge — no conflicts
# possible. The aux branch starts clean from the target base and receives only
# the files that the feature branch added.
#
# All derived automatically from the feature branch name:
#   repo       — read from config.json (same directory as this script's project root)
#   base_name  — stem of the .xlsx file found in the feature branch
#   ticket_id  — extracted from the feature branch commit message ([TICKET] desc)
#   description — extracted from the feature branch commit message
#
# Usage:
#   ./scripts/create_aux_branches.sh <feature_branch>
#
# Example:
#   ./scripts/create_aux_branches.sh feature/ZNRX_67108_renov_agosto
#
# Output branches pushed to origin:
#   {base_name}_developer_auxiliar
#   {base_name}_test_auxiliar
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
FEATURE_BRANCH="${1:?Usage: $0 <feature_branch>}"

# ---------------------------------------------------------------------------
# Resolve repo from config.json (one level up from scripts/)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.json"

[ -f "$CONFIG_FILE" ] \
  || { echo "ERROR: config.json not found at $CONFIG_FILE" >&2; exit 1; }

# Extract repo value with python (already available in the conda env)
REPO_PATH="$(python3 -c "import json,sys; print(json.load(open('$CONFIG_FILE'))['repo'])")"
# Resolve relative path from project root
REPO="$(cd "$PROJECT_ROOT/$REPO_PATH" && pwd)"

# Target bases for the two aux branches
BASE_BRANCHES=("developer" "test")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "  $*"; }
step() { echo; echo "▶ $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
step "Pre-flight checks"

[ -d "$REPO/.git" ] || fail "Not a git repository: $REPO"
log "Repo : $REPO"

# Fetch everything so we have an up-to-date view of origin
log "Fetching origin..."
git -C "$REPO" fetch origin

# Verify feature branch exists on origin
git -C "$REPO" ls-remote --exit-code origin "$FEATURE_BRANCH" > /dev/null \
  || fail "Feature branch '$FEATURE_BRANCH' not found on origin"

# ---------------------------------------------------------------------------
# Detect migration files
# ---------------------------------------------------------------------------
step "Detecting migration files added by '$FEATURE_BRANCH'"
CHANGED_FILES=$(git -C "$REPO" diff --name-only --diff-filter=A \
  "origin/developer...origin/${FEATURE_BRANCH}")

[ -n "$CHANGED_FILES" ] || fail "No new files found in '$FEATURE_BRANCH' relative to origin/developer"

# Validate: must be exactly 2 files — one .xlsx and one .java
FILE_COUNT=$(echo "$CHANGED_FILES" | wc -l | tr -d ' ')
XLSX_FILE=$(echo "$CHANGED_FILES" | grep '\.xlsx$' || true)
JAVA_FILE=$(echo "$CHANGED_FILES" | grep '\.java$' || true)

[ "$FILE_COUNT" -eq 2 ]   || fail "Expected exactly 2 files (xlsx + java), found $FILE_COUNT: $CHANGED_FILES"
[ -n "$XLSX_FILE" ]        || fail "No .xlsx file found among changed files: $CHANGED_FILES"
[ -n "$JAVA_FILE" ]        || fail "No .java file found among changed files: $CHANGED_FILES"

XLSX_STEM="$(basename "$XLSX_FILE" .xlsx)"
JAVA_STEM="$(basename "$JAVA_FILE" .java)"
[ "$XLSX_STEM" = "$JAVA_STEM" ] \
  || fail "File name mismatch: '$XLSX_FILE' vs '$JAVA_FILE' — stems must match"

log "xlsx : $XLSX_FILE"
log "java : $JAVA_FILE"
log "Files validated ✓"

# ---------------------------------------------------------------------------
# Derive base_name, ticket_id, description from the feature branch
# ---------------------------------------------------------------------------
step "Deriving metadata from feature branch"

# base_name = stem of the xlsx file  (e.g. V2026_06_11_15_43_27__ZNRX_67108_VH_ren_data_ago_2026)
BASE_NAME="$XLSX_STEM"

# commit message of the tip of the feature branch  (e.g. "[ZNRX-67108] VH_ren_data_ago_2026")
FEATURE_COMMIT_MSG="$(git -C "$REPO" log -1 --format="%s" "origin/${FEATURE_BRANCH}")"

# ticket_id = content inside the first [...]  (e.g. ZNRX-67108)
TICKET_ID="$(echo "$FEATURE_COMMIT_MSG" | sed -n 's/^\[\([^]]*\)\].*/\1/p')"
[ -n "$TICKET_ID" ] || fail "Could not extract ticket ID from commit message: '$FEATURE_COMMIT_MSG'"

# description = everything after "[TICKET] "
DESCRIPTION="$(echo "$FEATURE_COMMIT_MSG" | sed 's/^\[[^]]*\] //')"
[ -n "$DESCRIPTION" ] || fail "Could not extract description from commit message: '$FEATURE_COMMIT_MSG'"

COMMIT_MSG="[${TICKET_ID}] ${DESCRIPTION}"

log "base_name   : $BASE_NAME"
log "ticket_id   : $TICKET_ID"
log "description : $DESCRIPTION"
log "commit msg  : $COMMIT_MSG"

# ---------------------------------------------------------------------------
# Create one aux branch per target base
# ---------------------------------------------------------------------------
for BASE in "${BASE_BRANCHES[@]}"; do
  AUX_BRANCH="${BASE_NAME}_${BASE}_auxiliar"

  step "Creating '$AUX_BRANCH' from origin/$BASE"

  # Verify base exists on origin
  git -C "$REPO" ls-remote --exit-code origin "$BASE" > /dev/null \
    || { log "WARNING: origin/$BASE not found — skipping"; continue; }

  # Return to a neutral branch before deleting (can't delete current branch)
  git -C "$REPO" checkout developer --quiet

  # Delete local aux branch if it already exists (idempotent re-run)
  if git -C "$REPO" show-ref --verify --quiet "refs/heads/$AUX_BRANCH"; then
    log "Local branch '$AUX_BRANCH' already exists — deleting before recreating"
    git -C "$REPO" branch -D "$AUX_BRANCH"
  fi

  # Create aux branch from the base
  git -C "$REPO" checkout -b "$AUX_BRANCH" "origin/$BASE"
  log "Checked out '$AUX_BRANCH' from origin/$BASE"

  # Copy each migration file from the feature branch (no merge)
  for REL_FILE in $CHANGED_FILES; do
    DEST="$REPO/$REL_FILE"
    mkdir -p "$(dirname "$DEST")"
    log "Copying $REL_FILE from $FEATURE_BRANCH ..."
    git -C "$REPO" show "origin/${FEATURE_BRANCH}:${REL_FILE}" > "$DEST"
  done

  # Stage and commit exactly those 2 files
  git -C "$REPO" add $CHANGED_FILES
  git -C "$REPO" commit -m "$COMMIT_MSG"
  log "Committed: $COMMIT_MSG"

  # Push to origin — force allowed because aux branches are agent-generated and never shared
  git -C "$REPO" push --force --set-upstream origin "$AUX_BRANCH"
  log "Pushed '$AUX_BRANCH' to origin ✓"

done

# ---------------------------------------------------------------------------
# Return to developer (clean state)
# ---------------------------------------------------------------------------
step "Returning repo to developer"
git -C "$REPO" checkout developer
log "Done"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "═══════════════════════════════════════════════════════"
echo "  Feature  : $FEATURE_BRANCH"
for BASE in "${BASE_BRANCHES[@]}"; do
  AUX_BRANCH="${BASE_NAME}_${BASE}_auxiliar"
  echo "  Aux ($BASE): $AUX_BRANCH"
done
echo "  Files    : $XLSX_FILE"
echo "             $JAVA_FILE"
echo "  Commit   : $COMMIT_MSG"
echo "═══════════════════════════════════════════════════════"
