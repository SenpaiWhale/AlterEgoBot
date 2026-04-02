#!/bin/bash

# Auto-push to GitHub using stored token
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ GITHUB_TOKEN secret not set. Add it in Replit Secrets."
    exit 1
fi

REPO="https://SenpaiWhale:${GITHUB_TOKEN}@github.com/SenpaiWhale/AlterEgoBot.git"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
MESSAGE="${1:-Auto-sync: $TIMESTAMP}"

git add .
git commit -m "$MESSAGE" 2>&1

RESULT=$(git push "$REPO" main --force 2>&1)
echo "$RESULT"

if echo "$RESULT" | grep -q "main -> main"; then
    echo "✅ Pushed to GitHub successfully at $TIMESTAMP"
else
    echo "⚠️ Push may have failed. Check output above."
fi
