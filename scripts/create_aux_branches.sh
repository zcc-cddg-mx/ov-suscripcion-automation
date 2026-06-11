#!/usr/bin/env bash
# =============================================================================
# create_aux_branches.sh
#
# General-purpose auxiliary branch creator.
#
# Given a feature branch, creates two auxiliary branches:
#   {feature_suffix}_developer_auxiliar   — based on origin/developer
#   {feature_suffix}_test_auxiliar        — based on origin/test
#
# Each aux branch receives exactly the files changed in the feature branch
# (additions, modifications, deletions) relative to developer — applied via
# 'git show' (no merge, no conflicts possible).
#
# The repo path is read from config.json in the project root.
#
# Usage:
#   ./scripts/create_aux_branches.sh <feature_branch>
#
# Example:
#   ./scripts/create_aux_branches.sh feature/ZNRX_67108_renov_agosto
#
# Output branches pushed to origin:
#   ZNRX_67108_renov_agosto_developer_auxiliar
#   ZNRX_67108_renov_agosto_test_auxiliar
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
FEATURE_BRANCH="${1:?Usage: $0 <feature_branch>}"

# ---------------------------------------------------------------------------
# Resolve repo from config.json
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config.json"

[ -f "$CONFIG_FILE" ] \
  || { echo "ERROR: config.json not found at $CONFIG_FILE" >&2; exit 1; }

REPO_PATH="$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['repo'])")"
REPO="$(cd "$PROJECT_ROOT/$REPO_PATH" && pwd)"

# Aux branch name: strip leading "feature/" (or any prefix before "/") if present
FEATURE_SUFFIX="${FEATURE_BRANCH##*/}"

# Target bases for aux branches
BASE_BRANCHES=("developer" "test")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { echo "  $*"; }
step() { echo; echo "▶ $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
step "Pre-flight checks"

[ -d "$REPO/.git" ] || fail "Not a git repository: $REPO"
log "Repo    : $REPO"
log "Feature : $FEATURE_BRANCH"

log "Fetching origin..."
git -C "$REPO" fetch origin

git -C "$REPO" ls-remote --exit-code origin "$FEATURE_BRANCH" > /dev/null \
  || fail "Feature branch '$FEATURE_BRANCH' not found on origin"

# ---------------------------------------------------------------------------
# Detect changes introduced by the feature branch
# ---------------------------------------------------------------------------
step "Detecting changes in '$FEATURE_BRANCH' relative to origin/developer"

# name-status: lines like "A path", "M path", "D path"
CHANGED_STATUS=$(git -C "$REPO" diff --name-status \
  "origin/developer...origin/${FEATURE_BRANCH}")

[ -n "$CHANGED_STATUS" ] \
  || fail "No changes found in '$FEATURE_BRANCH' relative to origin/developer"

# Summary for the user
ADDED=$(echo "$CHANGED_STATUS"    | grep -c '^A' || true)
MODIFIED=$(echo "$CHANGED_STATUS" | grep -c '^M' || true)
DELETED=$(echo "$CHANGED_STATUS"  | grep -c '^D' || true)
log "Changes: +${ADDED} added  ~${MODIFIED} modified  -${DELETED} deleted"

# Commit message from the tip of the feature branch (reused in aux commits)
COMMIT_MSG="$(git -C "$REPO" log -1 --format="%s" "origin/${FEATURE_BRANCH}")"
log "Commit  : $COMMIT_MSG"

# ---------------------------------------------------------------------------
# Create one aux branch per target base
# ---------------------------------------------------------------------------
for BASE in "${BASE_BRANCHES[@]}"; do
  AUX_BRANCH="${FEATURE_SUFFIX}_${BASE}_auxiliar"

  step "Creating '$AUX_BRANCH' from origin/$BASE"

  git -C "$REPO" ls-remote --exit-code origin "$BASE" > /dev/null \
    || { log "WARNING: origin/$BASE not found — skipping"; continue; }

  # Return to neutral branch before any delete
  git -C "$REPO" checkout developer --quiet

  # Delete local aux branch if it exists (idempotent re-run)
  if git -C "$REPO" show-ref --verify --quiet "refs/heads/$AUX_BRANCH"; then
    log "Local branch '$AUX_BRANCH' already exists — recreating"
    git -C "$REPO" branch -D "$AUX_BRANCH"
  fi

  # Cut aux branch clean from the base
  git -C "$REPO" checkout -b "$AUX_BRANCH" "origin/$BASE"
  log "Checked out '$AUX_BRANCH' from origin/$BASE"

  # Apply each changed file from the feature branch
  while IFS=$'\t' read -r STATUS REL_FILE; do
    case "$STATUS" in
      A|M)
        DEST="$REPO/$REL_FILE"
        mkdir -p "$(dirname "$DEST")"
        git -C "$REPO" show "origin/${FEATURE_BRANCH}:${REL_FILE}" > "$DEST"
        git -C "$REPO" add "$REL_FILE"
        log "${STATUS} $REL_FILE"
        ;;
      D)
        git -C "$REPO" rm --quiet --force "$REL_FILE" 2>/dev/null || true
        log "D $REL_FILE"
        ;;
    esac
  done <<< "$CHANGED_STATUS"

  git -C "$REPO" commit -m "$COMMIT_MSG"
  log "Committed: $COMMIT_MSG"

  # Force push — aux branches are agent-generated, never shared manually
  git -C "$REPO" push --force --set-upstream origin "$AUX_BRANCH"
  log "Pushed '$AUX_BRANCH' to origin ✓"

done

# ---------------------------------------------------------------------------
# Return to developer
# ---------------------------------------------------------------------------
step "Returning repo to developer"
git -C "$REPO" checkout developer --quiet
log "Done"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "═══════════════════════════════════════════════════════"
echo "  Feature  : $FEATURE_BRANCH"
for BASE in "${BASE_BRANCHES[@]}"; do
  echo "  Aux ($BASE): ${FEATURE_SUFFIX}_${BASE}_auxiliar"
done
echo "  Changes  : +${ADDED} added  ~${MODIFIED} modified  -${DELETED} deleted"
echo "  Commit   : $COMMIT_MSG"
echo "═══════════════════════════════════════════════════════"
