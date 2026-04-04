#!/bin/bash

# Push to GitHub using GITHUB_TOKEN via credential helper (avoids
# embedding secrets in URLs or leaking them to process lists).
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN secret not set. Add it in Replit Secrets."
    exit 1
fi

REPO_OWNER="SenpaiWhale"
REPO_NAME="AlterEgoBot"
REMOTE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
MESSAGE="${1:-Auto-sync: $TIMESTAMP}"

git add .
git commit -m "$MESSAGE" 2>&1

RESULT=$(git -c "credential.helper=!f(){ echo username=${REPO_OWNER}; echo password=${GITHUB_TOKEN}; };f" \
    push "$REMOTE_URL" main 2>&1)
echo "$RESULT"

if echo "$RESULT" | grep -q "main -> main"; then
    echo "✅ Pushed to GitHub successfully at $TIMESTAMP"
else
    echo "⚠️ Push may have failed. Check output above."
fi
