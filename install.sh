#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
skill_file="$script_dir/SKILL.md"
grill_me_file="$script_dir/grill-me.md"

skip_distill=0
case "${1:-}" in
  --skip-distill)
    skip_distill=1
    ;;
  "")
    ;;
  *)
    echo "usage: $0 [--skip-distill]" >&2
    exit 2
    ;;
esac

if [[ ! -f "$skill_file" ]]; then
  echo "error: SKILL.md not found next to install.sh" >&2
  exit 1
fi

skill_name="$(
  awk '
    NR == 1 && $0 == "---" { in_frontmatter = 1; next }
    in_frontmatter && $0 == "---" { exit }
    in_frontmatter && $0 ~ /^[[:space:]]*name:[[:space:]]*/ {
      sub(/^[[:space:]]*name:[[:space:]]*/, "", $0)
      gsub(/^[[:space:]"'\''"]+|[[:space:]"'\''"]+$/, "", $0)
      print $0
      exit
    }
  ' "$skill_file"
)"

if [[ -z "$skill_name" ]]; then
  echo "error: SKILL.md frontmatter must include name: <skill-name>" >&2
  exit 1
fi

if [[ ! "$skill_name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "error: invalid skill name '$skill_name'; use lowercase hyphen-case" >&2
  exit 1
fi

codex_root="${CODEX_HOME:-$HOME/.codex}/skills"
claude_root="${CLAUDE_HOME:-$HOME/.claude}/skills"
codex_dest="$codex_root/$skill_name"
claude_dest="$claude_root/$skill_name"

copy_skill_md() {
  local dest="$1"
  mkdir -p "$dest"
  install -m 0644 "$skill_file" "$dest/SKILL.md"
}

install_grill_me_if_missing() {
  local root="$1"
  local label="$2"
  local dest="$root/grill-me"

  if [[ -f "$dest/SKILL.md" ]]; then
    echo "grill-me already installed for $label: $dest"
    return
  fi

  if [[ ! -f "$grill_me_file" ]]; then
    echo "warning: grill-me.md not found; skipped grill-me install for $label" >&2
    return
  fi

  mkdir -p "$dest"
  install -m 0644 "$grill_me_file" "$dest/SKILL.md"
  echo "Installed grill-me for $label: $dest"
}

sync_optional_dir() {
  local name="$1"
  local dest="$2"
  local src="$script_dir/$name"

  if [[ -d "$src" ]]; then
    rm -rf "$dest/$name"
    mkdir -p "$dest"
    cp -R "$src" "$dest/$name"
  fi
}

copy_skill_md "$codex_dest"
sync_optional_dir "agents" "$codex_dest"
sync_optional_dir "assets" "$codex_dest"
sync_optional_dir "references" "$codex_dest"
sync_optional_dir "scripts" "$codex_dest"
sync_optional_dir "hidden" "$codex_dest"
sync_optional_dir "workflows" "$codex_dest"
install_grill_me_if_missing "$codex_root" "Codex"

copy_skill_md "$claude_dest"
sync_optional_dir "assets" "$claude_dest"
sync_optional_dir "references" "$claude_dest"
sync_optional_dir "scripts" "$claude_dest"
install_grill_me_if_missing "$claude_root" "Claude"

install_distill_deps() {
  echo "Installing distill dependencies..."
  if command -v crontab >/dev/null 2>&1; then
    bash "$script_dir/scripts/install_cron.sh" \
      || echo "warning: distill cron install failed; run scripts/install_cron.sh manually" >&2
  else
    echo "warning: crontab not found; skipped distill cron" >&2
  fi
  if [[ -w "$HOME" && -d "$HOME" ]]; then
    bash "$script_dir/scripts/install_login_hook.sh" \
      || echo "warning: distill login hook install failed; run scripts/install_login_hook.sh manually" >&2
  else
    echo "warning: HOME not writable; skipped distill login hook" >&2
  fi
}

if [[ "$skip_distill" -eq 0 ]]; then
  install_distill_deps
fi

echo "Installed $skill_name for Codex:  $codex_dest"
echo "Installed $skill_name for Claude: $claude_dest"
echo "Restart Codex to pick up new skills. Restart Claude Code if ~/.claude/skills did not exist when the session started."
