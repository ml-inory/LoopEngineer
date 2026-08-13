#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
prompt="$repo_dir/scripts/cron_prompt.txt"
marker="# loop-engineer-distill"

crontab -l >/tmp/le_cron_backup.txt 2>/dev/null || true
if grep -qF "$marker" /tmp/le_cron_backup.txt; then
  echo "cron entries already installed; remove them manually to reinstall (backup: /tmp/le_cron_backup.txt)"
  exit 0
fi

log_dir="$repo_dir/digests"
mkdir -p "$log_dir"

{
  cat /tmp/le_cron_backup.txt
  echo "$marker"
  echo "0 7 * * * cd $repo_dir && codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox < $prompt >> $log_dir/cron.log 2>&1"
  echo "0 23 * * * cd $repo_dir && codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox < $prompt >> $log_dir/cron.log 2>&1"
  echo "$marker-end"
} | crontab -

echo "installed cron: 07:00 / 23:00 daily (backup: /tmp/le_cron_backup.txt)"
crontab -l | grep -F "$marker" | tail -3
