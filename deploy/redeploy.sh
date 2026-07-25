#!/usr/bin/env bash
#
# Reproducible, drift-free deploy from a local git checkout to the EC2 box.
#
#   deploy/redeploy.sh [all|backend|frontend] [--allow-dirty] [--reindex]
#
# Why this exists (deployment hygiene):
#   * Syncs the EXACT git-tracked source with rsync --delete, so the box can
#     never silently drift from the repo (the old per-file rsync could).
#   * Stamps the deployed commit on the box (~/clm/DEPLOYED_COMMIT) for an audit
#     trail + a rollback reference.
#   * Rebuilds images fresh (frontend with --no-cache, which plain
#     `docker-compose build` skips — the reason frontend changes used to not
#     show up) and runs `alembic upgrade head`.
#   * Verifies health and prints a changelog vs the previously-deployed commit.
#
# Rollback: `git checkout <sha> && deploy/redeploy.sh` re-deploys that exact commit.
set -euo pipefail

HOST="${CLM_HOST:-ec2-user@52.21.204.211}"
KEY="${CLM_KEY:-$HOME/.ssh/clm-demo-key.pem}"
APP_URL="${CLM_URL:-http://52.21.204.211}"
REMOTE_DIR="clm"                                    # relative to ec2-user home
COMPOSE="docker-compose -f docker-compose.prod.yml" # box uses standalone v1

TARGET="all"; ALLOW_DIRTY=false; REINDEX=false
for a in "$@"; do
  case "$a" in
    all|backend|frontend) TARGET="$a" ;;
    --allow-dirty) ALLOW_DIRTY=true ;;
    --reindex) REINDEX=true ;;
    *) echo "Unknown arg: $a"; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SSH_CMD=(ssh -i "$KEY")

# ── 1. Commit identity + cleanliness guard ───────────────────────────
COMMIT=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
DIRTY=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$DIRTY" != "0" ] && [ "$ALLOW_DIRTY" = false ]; then
  echo "ERROR: $DIRTY uncommitted change(s). Commit first (deploys should be a known commit), or pass --allow-dirty."
  git status -s | head
  exit 1
fi
DIRTY_TAG=""; [ "$DIRTY" != "0" ] && DIRTY_TAG=" [dirty]"
STAMP="$COMMIT ($BRANCH) $(date -u +%FT%TZ) by $(whoami)$DIRTY_TAG"

echo "==> Deploy target=$TARGET  commit=$STAMP  ->  $HOST"
PREV=$("${SSH_CMD[@]}" "$HOST" "cat $REMOTE_DIR/DEPLOYED_COMMIT 2>/dev/null | head -1" 2>/dev/null || true)
[ -n "$PREV" ] && echo "    previously deployed: $PREV"

# ── 2. Drift-free source sync (only the requested tree; whole dir, --delete) ──
EXCLUDES=(--exclude __pycache__ --exclude '*.pyc' --exclude .venv
          --exclude node_modules --exclude dist --exclude .git
          --exclude storage --exclude .env --exclude '*.sqlite*')
sync_dir() {
  echo "==> Syncing $1/ (rsync --delete)"
  rsync -az --delete "${EXCLUDES[@]}" -e "ssh -i $KEY" \
    "$ROOT/$1/" "$HOST:$REMOTE_DIR/$1/"
}
if [ "$TARGET" = "backend" ]  || [ "$TARGET" = "all" ]; then sync_dir backend; fi
if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "all" ]; then sync_dir frontend; fi
sync_dir deploy
"${SSH_CMD[@]}" "$HOST" "printf '%s\n' '$STAMP' > $REMOTE_DIR/DEPLOYED_COMMIT"

# ── 3. Build + restart + migrate on the box ──────────────────────────
echo "==> Building + starting on the box"
"${SSH_CMD[@]}" "$HOST" bash -s <<EOF
set -e
cd $REMOTE_DIR/deploy
if [ "$TARGET" = "backend" ] || [ "$TARGET" = "all" ]; then
  $COMPOSE build backend
  $COMPOSE up -d backend
  echo "    waiting for backend..."; sleep 12
  $COMPOSE exec -T backend alembic upgrade head
fi
if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "all" ]; then
  $COMPOSE build --no-cache frontend
  $COMPOSE up -d frontend
fi
if [ "$REINDEX" = "true" ]; then
  $COMPOSE exec -T backend python -m scripts.reindex_clauses || true
fi
EOF

# ── 4. Health check ──────────────────────────────────────────────────
echo "==> Health:"
ok=true
for p in / /api/health; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL$p" || echo 000)
  echo "    $APP_URL$p -> $code"
  [ "$code" = "200" ] || ok=false
done

# ── 5. Changelog since previous deploy ───────────────────────────────
if [ -n "$PREV" ]; then
  PREV_SHA=$(echo "$PREV" | awk '{print $1}')
  if git cat-file -e "$PREV_SHA" 2>/dev/null; then
    echo "==> Changes since $PREV_SHA:"
    git log --oneline "$PREV_SHA..$COMMIT" | sed 's/^/    /' | head -25
  fi
fi

$ok && echo "==> Done. Deployed $COMMIT ($TARGET)." || { echo "==> WARNING: health check did not return 200 — verify manually."; exit 1; }
