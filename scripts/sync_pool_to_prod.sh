#!/usr/bin/env bash
# Apply a pool_export.sql (from db_export_pool.py) to production ToolsDB over
# an SSH tunnel. Content is authored and reviewed locally; this is the manual
# promotion step. See docs/deployment-toolforge.md.
#
# Usage:
#   scripts/db_export_pool.py --since-id 42 > /tmp/pool_export.sql
#   TOOLFORGE_USER=myuser scripts/sync_pool_to_prod.sh /tmp/pool_export.sql

set -euo pipefail

EXPORT_FILE="${1:?usage: sync_pool_to_prod.sh <export.sql>}"
TOOLFORGE_USER="${TOOLFORGE_USER:?set TOOLFORGE_USER}"
TUNNEL_PORT="${TUNNEL_PORT:-3307}"
DB_NAME="${DB_NAME:-wikiwhiz}"

echo "Opening SSH tunnel to ToolsDB via login.toolforge.org..."
ssh -f -N -L "${TUNNEL_PORT}:tools.db.svc.wikimedia.cloud:3306" \
    "${TOOLFORGE_USER}@login.toolforge.org"
TUNNEL_PID=$(pgrep -f "L ${TUNNEL_PORT}:tools.db.svc.wikimedia.cloud:3306" | head -1)

cleanup() {
    [ -n "${TUNNEL_PID:-}" ] && kill "${TUNNEL_PID}" 2>/dev/null || true
}
trap cleanup EXIT

echo "Applying ${EXPORT_FILE} to ${DB_NAME}..."
mysql -h 127.0.0.1 -P "${TUNNEL_PORT}" -u "${DB_USER:?set DB_USER}" -p"${DB_PASSWORD:?set DB_PASSWORD}" \
    "${DB_NAME}" < "${EXPORT_FILE}"

echo "Done."
