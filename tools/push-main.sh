#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."

remote_url='https://github.com/Nehsto/agent-sandbox.git'
if ! git rev-parse --git-dir >/dev/null 2>&1; then
    git init -b main
fi

if ! git var GIT_AUTHOR_IDENT >/dev/null 2>&1; then
    echo 'Configure your commit identity locally, then rerun this script:' >&2
    echo '  git config user.name "Your Name"' >&2
    echo '  git config user.email "Your GitHub commit email"' >&2
    exit 1
fi

branch=$(git symbolic-ref --short HEAD)
if [[ "$branch" != main ]]; then
    echo "Current branch is $branch; switch to main before running this script." >&2
    exit 1
fi

if git remote get-url origin >/dev/null 2>&1; then
    if [[ "$(git remote get-url origin)" != "$remote_url" ]]; then
        echo 'Existing origin differs from the requested repository; inspect git remote -v.' >&2
        exit 1
    fi
else
    git remote add origin "$remote_url"
fi

# Check connectivity/authentication before creating the commit.
git ls-remote origin >/dev/null
git add -- .gitignore README.md codex/ bt/ ui/ tools/ test/ requirements.txt dashboard.py agent_status.py previews/
if ! git diff --cached --quiet; then
    git commit -m "Add Raspberry Pi companion interface and Bluetooth diagnostics"
fi
# Normal push: an existing divergent main is rejected, never overwritten.
git push -u origin main
