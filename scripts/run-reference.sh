#!/bin/sh
# Run the conformance suite against the PHP reference implementation
# (ks-sw-api) on `php -S` in docker.
#
#   scripts/run-reference.sh IMPL_DIR [pytest args...]
#
# IMPL_DIR is a checkout of ks-sw-api. Its test settings
# (tests/config.test.php: X-Forwarded-For trusted, admin over plain http,
# a public test token) are used; never on a real server.
# Environment: PHP_IMAGE (default php:8.3-cli), PORT (default 8790),
# PYTEST (default: pytest through uv).
set -eu

IMPL_DIR=$(cd "$1" && pwd)
shift
PHP_IMAGE=${PHP_IMAGE:-php:8.3-cli}
PORT=${PORT:-8790}
PYTEST=${PYTEST:-uv run --no-project --with pytest pytest -q}
NAME=kssw-spec-reference-$PORT
BASE_URL=http://127.0.0.1:$PORT
# The token whose SHA-256 is in ks-sw-api's tests/config.test.php. Public:
# it only ever opens a throwaway test server.
ADMIN_TOKEN=${ADMIN_TOKEN:-kssw-test-admin-token-public-never-use}

test -f "$IMPL_DIR/php/api/index.php" || { echo "$IMPL_DIR is not a ks-sw-api checkout" >&2; exit 2; }

docker rm -f "$NAME" >/dev/null 2>&1 || true
docker run -d --rm --name "$NAME" -p "127.0.0.1:$PORT:8080" -e KSSW_CONFIG=/conf/config.test.php \
	-v "$IMPL_DIR/php/api:/app:ro" -v "$IMPL_DIR/tests:/conf:ro" \
	"$PHP_IMAGE" php -q -S 0.0.0.0:8080 -t /app /app/index.php >/dev/null
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT INT TERM

i=0
until curl -fsS "$BASE_URL/v1/meta" >/dev/null 2>&1; do
	i=$((i + 1))
	if [ "$i" -gt 120 ]; then
		echo "reference server did not come up" >&2
		docker logs "$NAME" >&2 || true
		exit 1
	fi
	sleep 0.5
done

cd "$(dirname "$0")/.."
BASE_URL=$BASE_URL ADMIN_TOKEN=$ADMIN_TOKEN $PYTEST conformance "$@"
