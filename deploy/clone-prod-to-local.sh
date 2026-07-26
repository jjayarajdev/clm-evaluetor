#!/usr/bin/env bash
#
# Clone the AWS prod Postgres into a LOCAL Docker Postgres 15 for browsing
# (Beekeeper Studio, psql, etc.). One-way snapshot — safe to re-run anytime to
# refresh local with the latest prod data. Never writes back to prod.
#
#   deploy/clone-prod-to-local.sh
#
# Result: postgres:15 container "clm-aws-clone" on localhost:5433 (clm/clm/clm).
# Local port 5433 is used because a native Postgres already owns 5432.
set -euo pipefail

HOST="${CLM_HOST:-ec2-user@52.21.204.211}"
KEY="${CLM_KEY:-$HOME/.ssh/clm-demo-key.pem}"
REMOTE_PG="deploy-postgres-1"          # prod postgres container on the box
LOCAL_NAME="clm-aws-clone"
LOCAL_PORT="${CLM_LOCAL_PG_PORT:-5433}"

echo "==> (Re)creating local $LOCAL_NAME (postgres:15) on localhost:$LOCAL_PORT"
docker rm -f "$LOCAL_NAME" >/dev/null 2>&1 || true
docker run -d --name "$LOCAL_NAME" \
  -e POSTGRES_USER=clm -e POSTGRES_PASSWORD=clm -e POSTGRES_DB=clm \
  -p "$LOCAL_PORT:5432" postgres:15-alpine >/dev/null

echo "==> Waiting for readiness"
for _ in $(seq 1 30); do
  docker exec "$LOCAL_NAME" pg_isready -U clm >/dev/null 2>&1 && break
  sleep 1
done

echo "==> Dumping prod ($REMOTE_PG) and restoring into the clone"
ssh -i "$KEY" "$HOST" \
  "docker exec $REMOTE_PG pg_dump -U clm -d clm --no-owner --no-privileges" \
  | docker exec -i "$LOCAL_NAME" psql -U clm -d clm -q -v ON_ERROR_STOP=0

echo "==> Done. Row counts:"
docker exec "$LOCAL_NAME" psql -U clm -d clm -tAc \
  "SELECT 'contracts='||count(*) FROM contracts
   UNION ALL SELECT 'users='||count(*) FROM users
   UNION ALL SELECT 'tenants='||count(*) FROM tenants;"
echo "==> Connect: host=localhost port=$LOCAL_PORT db=clm user=clm password=clm"
