#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./scripts/publish_standalone_repo.sh <git-remote-url>"
    exit 1
fi

REPO_URL=$1
echo "Publishing Parallax to: $REPO_URL"

git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"
git branch -M main
git push -u origin main

echo "Published successfully to $REPO_URL!"
echo "Next steps:"
echo "1. Tag a release: git tag v0.1.0 && git push origin v0.1.0"
echo "2. Build PyPI wheel: uv build"
echo "3. Publish to PyPI: twine upload dist/*"
