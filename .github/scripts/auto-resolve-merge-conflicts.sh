#!/usr/bin/env bash
# Auto-resolve common merge conflicts after `git merge <upstream-tag>`.
# Called by .github/workflows/sync-upstream.yml.
#
# Resolution rules:
#   - VERSION_FILES (mix.exs, CHANGELOG.md, etc.): always take upstream content
#   - .github/workflows/* in KEEP_WORKFLOWS: keep DOS version
#       (these files are DOS-authored and must survive when upstream renames/deletes them)
#   - .github/workflows/* not in KEEP_WORKFLOWS: prefer upstream content,
#       accept either side's deletion (upstream-only files get pruned in the next step anyway)
#
# After this script runs, `git status` may still show unmerged paths for content
# conflicts in non-workflow files. Exits 0 when fully resolved, 1 when conflicts remain.
#
# NOTE: deliberately does NOT use `set -e` so a single file failure does not
# abort the whole batch (previous bug: a single `xargs git checkout --theirs`
# failure on a modify/delete conflict killed the entire step with exit 123).

set -uo pipefail

VERSION_FILES=(
  mix.exs
  rel/config.exs
  docker/Makefile
  CHANGELOG.md
  apps/block_scout_web/mix.exs
  apps/ethereum_jsonrpc/mix.exs
  apps/explorer/mix.exs
  apps/indexer/mix.exs
  apps/nft_media_handler/mix.exs
  apps/utils/mix.exs
)

KEEP_WORKFLOWS=(
  .github/workflows/deploy-config.yml
  .github/workflows/publish-regular-docker-image-on-demand.yml
  .github/workflows/sync-upstream.yml
)

is_in_array() {
  local needle="$1"; shift
  local hay
  for hay in "$@"; do [ "$hay" = "$needle" ] && return 0; done
  return 1
}

# `git status --porcelain` unmerged status codes (XY columns, see git-status(1)):
#   DD  both deleted
#   AU  added by us
#   UD  deleted by them   (we modified, they deleted)
#   UA  added by them
#   DU  deleted by us     (we deleted, they modified)
#   AA  both added
#   UU  both modified
while IFS= read -r line; do
  [ -z "$line" ] && continue
  status="${line:0:2}"
  file="${line:3}"

  # VERSION_FILES: always take upstream (content conflict only)
  if is_in_array "$file" "${VERSION_FILES[@]}"; then
    case "$status" in
      UU|AU|UA)
        echo "  Resolve VERSION (theirs): $file"
        if git checkout --theirs -- "$file" 2>/dev/null; then
          git add -- "$file"
        else
          echo "::warning::Cannot checkout --theirs for $file ($status)"
        fi
        continue
        ;;
    esac
  fi

  # .github/workflows/*
  if [[ "$file" == .github/workflows/* ]]; then
    case "$status" in
      DU)
        # We deleted, upstream modified - keep our deletion.
        echo "  Resolve workflow (keep our deletion): $file"
        git rm -f -- "$file" >/dev/null 2>&1 || true
        ;;
      UD)
        # We modified, upstream deleted.
        if is_in_array "$file" "${KEEP_WORKFLOWS[@]}"; then
          echo "  Resolve workflow (keep ours; upstream deleted): $file"
          git add -- "$file"
        else
          echo "  Resolve workflow (drop; upstream deleted): $file"
          git rm -f -- "$file" >/dev/null 2>&1 || true
        fi
        ;;
      UU|AU|UA)
        if is_in_array "$file" "${KEEP_WORKFLOWS[@]}"; then
          echo "  Resolve workflow (keep ours; content conflict): $file"
          git checkout --ours -- "$file" && git add -- "$file"
        else
          echo "  Resolve workflow (theirs; content conflict): $file"
          if git checkout --theirs -- "$file" 2>/dev/null; then
            git add -- "$file"
          else
            echo "::warning::Cannot checkout --theirs for $file ($status)"
          fi
        fi
        ;;
      DD)
        echo "  Resolve workflow (both deleted): $file"
        git rm -f -- "$file" >/dev/null 2>&1 || true
        ;;
      *)
        echo "::warning::Unhandled workflow conflict status $status for $file"
        ;;
    esac
    continue
  fi
done < <(git status --porcelain | grep -E '^(UU|DU|UD|AA|DD|AU|UA) ' || true)

# Report remaining conflicts; caller decides whether to abort or proceed (e.g. for PR fallback).
REMAINING=$(git diff --name-only --diff-filter=U)
if [ -n "$REMAINING" ]; then
  echo "::warning::Remaining unresolved conflicts:"
  echo "$REMAINING" | sed 's/^/  - /'
  exit 1
fi

exit 0
