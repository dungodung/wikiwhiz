#!/usr/bin/env bash
# Build the React frontend to static assets and copy them into Flask's
# static folder, so `FLASK_ENV=production flask --app wsgi run` (or the
# deployed gunicorn process) can serve them directly. Needed because
# Toolforge Build Service images support only one primary language runtime,
# so Node can't run as part of the Python build -- see docs/deployment-toolforge.md.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "${REPO_ROOT}/frontend"
npm ci
npm run build

rsync -a --delete "${REPO_ROOT}/frontend/dist/" "${REPO_ROOT}/backend/app/static/"
echo "Frontend built and copied to backend/app/static/"
