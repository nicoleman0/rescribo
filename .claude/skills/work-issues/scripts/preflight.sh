#!/usr/bin/env bash
# Check batch requirements before creating a worktree.
# Provider gaps warn so the coordinator can still run every worker role.
set -u

missing=0
warnings=0

required() {
  local name=$1
  local command=$2
  local fix=$3
  if command -v "$command" >/dev/null 2>&1; then
    printf 'ok       %s\n' "$name"
  else
    printf 'MISSING  %s: not installed. %s\n' "$name" "$fix"
    missing=$((missing + 1))
  fi
}

warning() {
  printf 'warn     %s\n' "$1"
  warnings=$((warnings + 1))
}

required git git 'Install Git with your system package manager.'
required 'Python 3' python3 'Install Python 3 from python.org or your system package manager.'

if command -v node >/dev/null 2>&1 && command -v npx >/dev/null 2>&1; then
  printf 'ok       Node.js\n'
else
  printf 'MISSING  Node.js: node and npx are required. Install Node.js.\n'
  missing=$((missing + 1))
fi

if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    printf 'ok       GitHub CLI\n'
  else
    printf 'MISSING  GitHub CLI: not signed in. Run: gh auth login\n'
    missing=$((missing + 1))
  fi
else
  printf 'MISSING  GitHub CLI: not installed. Install from https://cli.github.com\n'
  missing=$((missing + 1))
fi

provider_count=0
installed_count=0
installed_provider=""
for provider in "$@"; do
  provider_count=$((provider_count + 1))
  if type -P "$provider" >/dev/null 2>&1; then
    printf 'ok       Provider %s\n' "$provider"
    installed_count=$((installed_count + 1))
    installed_provider=$provider
  else
    printf 'warn     Provider %s: not installed. The coordinator leaves it out.\n' "$provider"
    warnings=$((warnings + 1))
  fi
done

if [ "$provider_count" -eq 0 ]; then
  warning 'Worker providers: none named. Pass the providers in routing.md: preflight.sh <provider>...'
elif [ "$installed_count" -eq 0 ]; then
  warning 'Worker providers: none of the named providers is installed. The coordinator will choose one and tell you.'
elif [ "$installed_count" -eq 1 ]; then
  warning "Second provider: only $installed_provider is installed. The reviewer runs on the implementer's provider, so the review is not independent."
else
  printf 'ok       Second provider\n'
fi

if command -v herdr >/dev/null 2>&1; then
  printf 'ok       Herdr\n'
else
  warning 'Herdr: not installed. Workers will run headless. See https://herdr.dev'
fi

if command -v node >/dev/null 2>&1; then
  # Match the package lookup used by shots.mjs.
  if node -e 'require.resolve("@playwright/test", { paths: [process.env.SHOTS_PACKAGE_DIR || "."] })' >/dev/null 2>&1; then
    printf 'ok       Playwright\n'
  else
    warning 'Playwright: @playwright/test not found. UI screenshots will not work.'
  fi
else
  warning 'Playwright: skipped because Node.js is missing. UI screenshots will not work.'
fi

if command -v sips >/dev/null 2>&1 || command -v magick >/dev/null 2>&1; then
  printf 'ok       Image tool\n'
else
  warning 'Image tool: install sips or ImageMagick. The comparison page cannot be built.'
fi

if [ -f AGENTS.md ]; then
  placeholder="Replace this section with your project's rules."
  in_project=0
  while IFS= read -r line; do
    case $line in
      '## Project') in_project=1 ;;
      '## '*) in_project=0 ;;
    esac
    if [ "$in_project" -eq 1 ] && [[ $line == *"$placeholder"* ]]; then
      warning 'AGENTS.md Project section: still the shipped placeholder. Fill it in with your checks, shared services, and conventions; every session reads it.'
      break
    fi
  done < AGENTS.md
fi

printf '%s missing, %s warning(s)\n' "$missing" "$warnings"
[ "$missing" -eq 0 ]
