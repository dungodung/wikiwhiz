#!/usr/bin/env bash
# One-time local dev machine setup: installs Docker Engine + the `docker
# compose` plugin via Docker's official convenience script, then adds the
# invoking (non-root) user to the `docker` group so `docker`/`docker compose`
# can be run without sudo afterwards.
#
# You do NOT need a separate MySQL/MariaDB install: docker-compose.yml runs
# MariaDB as a container (`docker compose up -d db`) -- that's the only
# database WikiWhiz needs for local development.
#
# Run this with sudo, as yourself (not as root directly), so $SUDO_USER
# resolves correctly:
#   sudo bash scripts/install-docker-dev.sh

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this with sudo: sudo bash scripts/install-docker-dev.sh" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-$(logname)}"

echo "==> Installing Docker Engine via get.docker.com ..."
curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
sh /tmp/get-docker.sh
rm -f /tmp/get-docker.sh

echo "==> Enabling and starting the docker service ..."
systemctl enable --now docker

echo "==> Adding ${TARGET_USER} to the docker group ..."
usermod -aG docker "${TARGET_USER}"

echo
echo "Done. Log out and back in (or run 'newgrp docker') for the group"
echo "membership to take effect, then verify with:"
echo "  docker run hello-world"
echo "  docker compose version"
