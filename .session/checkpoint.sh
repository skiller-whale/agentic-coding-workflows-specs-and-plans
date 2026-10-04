#!/usr/bin/env bash
# Resets the city exercise to a checkpoint: start, deliveries or busy. Run by the /checkpoint skill.
# Session plumbing, not part of the exercise. Replaces everything the exercise works on (code, tests,
# openspec/) with the checkpoint's copy from checkpoints.tar.gz. The learner's work isn't kept.
set -euo pipefail
NAME="${1:-}"
case "$NAME" in start|deliveries|busy) ;; *) echo "Usage: checkpoint.sh start|deliveries|busy" >&2; exit 2 ;; esac
REPO="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVE="$REPO/.session/checkpoints.tar.gz"
# Session and editor plumbing that a checkpoint never touches.
KEEP=" .claude .session .vscode .git .gitignore setup.sh docker-compose.yml docker-compose.override.yml attendance_id .curriculumconfig "
cd "$REPO"
shopt -s dotglob nullglob
for path in *; do
  [[ "$KEEP" == *" $path "* ]] || rm -rf -- "$path"
done
tar -xzf "$ARCHIVE" --strip-components=1 "$NAME/"
mkdir -p "$HOME/.city-session"
printf '{"name": "%s", "time": "%s"}\n' "$NAME" "$(date +%H:%M)" > "$HOME/.city-session/checkpoint.json"
echo "Checkpoint loaded: $NAME"
