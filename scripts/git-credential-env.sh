#!/usr/bin/env bash
# Git credential helper that reads a GitHub PAT from this project's .env file.
# Keeps the token per-project (multiple repos on this machine each have their own .env)
# and out of $HOME-wide credential stores.
#
# Configure once per clone:
#   git config --local credential.helper "$(pwd)/scripts/git-credential-env.sh"
#
# Expects a line like the following in <repo-root>/.env:
#   github_PAT_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

set -eu

# Only respond to the 'get' operation; ignore 'store' and 'erase' so git can
# never overwrite or wipe the .env-managed token behind our back.
[ "${1:-}" = "get" ] || exit 0

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$ROOT" ] || [ ! -f "$ROOT/.env" ]; then
  exit 0
fi

TOKEN="$(grep -E '^github_PAT_TOKEN=' "$ROOT/.env" | head -n1 | cut -d= -f2-)"
if [ -z "$TOKEN" ]; then
  exit 0
fi

printf 'username=x-access-token\npassword=%s\n' "$TOKEN"
