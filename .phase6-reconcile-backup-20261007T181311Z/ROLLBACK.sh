#!/usr/bin/env bash
set -euo pipefail
TARGET="/home/kiyingijmc/projects/FractalFlow"
BACKUP="/home/kiyingijmc/projects/FractalFlow/.phase6-reconcile-backup-20261007T181311Z"
while IFS= read -r -d '' f; do
  rel="${f#$BACKUP/}"
  [[ "$rel" == "git-status-before.txt" || "$rel" == "head-before.txt" ]] && continue
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp -p "$f" "$TARGET/$rel"
done < <(find "$BACKUP" -type f -print0)
echo "Restored overwritten files from $BACKUP"
