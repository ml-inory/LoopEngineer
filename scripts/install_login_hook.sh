#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
inbox="$repo_dir/digests/inbox.md"
bashrc="$HOME/.bashrc"
start='# >>> loop-engineer distill inbox >>>'
end='# <<< loop-engineer distill inbox <<<'

if [[ ! -f "$bashrc" ]]; then
  touch "$bashrc"
fi

tmp="$(mktemp)"
sed "/^$start$/,/^$end$/d" "$bashrc" > "$tmp"
cat >> "$tmp" <<EOF
$start
if [ -f "$inbox" ] && [ -s "$inbox" ]; then
  echo "[LoopEngineer] \$(wc -l < "$inbox") 条蒸馏待办，查看: $inbox"
fi
$end
EOF
mv "$tmp" "$bashrc"
echo "login hook installed in $bashrc"
