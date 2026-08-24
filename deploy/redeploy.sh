#!/usr/bin/env bash
#
# Reproducible, drift-free deploy from a local git checkout to the EC2 box.
#
#   deploy/redeploy.sh [all|backend|frontend] [--cell=us|eu] [--allow-dirty] [--reindex]
#
# Cells (data-residency regions): each cell is a full stack on its own box.
#   Connection details live in deploy/cells/<name>.env (CLM_HOST/CLM_KEY/CLM_URL).
#   Default cell is "us". App secrets are NOT in these files — they live in the
#   per-box deploy/.env, which rsync excludes.
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

REMOTE_DIR="clm"                                    # relative to ec2-user home
COMPOSE="docker-compose -f docker-compose.prod.yml" # box uses standalone v1

CELL="${CLM_CELL:-us}"
TARGET="all"; ALLOW_DIRTY=false; REINDEX=false
for a in "$@"; do
  case "$a" in
    all|backend|frontend) TARGET="$a" ;;
    --cell=*) CELL="${a#--cell=}" ;;
    --allow-dirty) ALLOW_DIRTY=true ;;
    --reindex) REINDEX=true ;;
    *) echo "Unknown arg: $a"; exit 2 ;;
  esac
done

CELL_FILE="$(dirname "${BASH_SOURCE[0]}")/cells/$CELL.env"
if [ ! -f "$CELL_FILE" ]; then
  echo "ERROR: unknown cell '$CELL' (no $CELL_FILE)"; exit 2
fi
# shellcheck source=/dev/null
source "$CELL_FILE"
HOST="${CLM_HOST:?cell file must set CLM_HOST}"
KEY="${CLM_KEY:-$HOME/.ssh/clm-demo-key.pem}"
APP_URL="${CLM_URL:?cell file must set CLM_URL}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
SSH_CMD=(ssh -i "$KEY")

# ── 1. Commit identity + cleanliness guard ───────────────────────────
COMMIT=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)
# Only tracked changes matter — they would make the deployed code differ from
# the commit. Untracked files aren't committed and aren't synced, so ignore them.
DIRTY=$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')
if [ "$DIRTY" != "0" ] && [ "$ALLOW_DIRTY" = false ]; then
  echo "ERROR: $DIRTY uncommitted change(s) to tracked files. Commit first (deploy a known commit), or pass --allow-dirty."
  git status -s --untracked-files=no | head
  exit 1
fi
DIRTY_TAG=""; [ "$DIRTY" != "0" ] && DIRTY_TAG=" [dirty]"
STAMP="$COMMIT ($BRANCH) $(date -u +%FT%TZ) by $(whoami)$DIRTY_TAG"

echo "==> Deploy cell=$CELL  target=$TARGET  commit=$STAMP  ->  $HOST"
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
# Order matters: build AND start both images BEFORE the DB migrate, so a
# migrate failure (which would trip `set -e`) can never skip the frontend
# rebuild — the bug that once shipped a stale frontend on an `all` deploy.
echo "==> Building + starting on the box"
"${SSH_CMD[@]}" "$HOST" bash -s <<EOF
set -e
cd $REMOTE_DIR/deploy
if [ "$TARGET" = "backend" ]  || [ "$TARGET" = "all" ]; then $COMPOSE build backend; fi
if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "all" ]; then $COMPOSE build --no-cache frontend; fi
if [ "$TARGET" = "backend" ]  || [ "$TARGET" = "all" ]; then $COMPOSE up -d backend; fi
if [ "$TARGET" = "frontend" ] || [ "$TARGET" = "all" ]; then $COMPOSE up -d frontend; fi
if [ "$TARGET" = "backend" ]  || [ "$TARGET" = "all" ]; then
  echo "    waiting for backend..."; sleep 12
  $COMPOSE exec -T backend alembic upgrade head
fi
if [ "$REINDEX" = "true" ]; then
  $COMPOSE exec -T backend python -m scripts.reindex_clauses || true
fi
EOF

# ── 3b. Reclaim disk (build cache once filled the 30G root disk to 99%,
# failing mid-deploy with "I/O operation failed during extraction"). Keep a
# bounded build cache so backend layer-caching still works; drop images no
# longer referenced by a container (rollback is rebuild-from-source anyway).
echo "==> Pruning docker build cache (>8GB) + dangling images"
"${SSH_CMD[@]}" "$HOST" \
  "docker builder prune -f --keep-storage 8GB >/dev/null 2>&1 || docker builder prune -f >/dev/null 2>&1 || true; \
   docker image prune -f >/dev/null 2>&1 || true; \
   df -h / | tail -1" || true

# ── 4. Health check (poll — a freshly-restarted backend needs a moment) ──
echo "==> Health (polling up to ~60s):"
ok=false; front=000; api=000
for _ in $(seq 1 20); do
  front=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/" || echo 000)
  api=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/api/health" || echo 000)
  if [ "$front" = "200" ] && [ "$api" = "200" ]; then ok=true; break; fi
  sleep 3
done
echo "    $APP_URL/ -> $front   $APP_URL/api/health -> $api"

# ── 5. Changelog since previous deploy ───────────────────────────────
if [ -n "$PREV" ]; then
  PREV_SHA=$(echo "$PREV" | awk '{print $1}')
  if git cat-file -e "$PREV_SHA" 2>/dev/null; then
    echo "==> Changes since $PREV_SHA:"
    git log --oneline "$PREV_SHA..$COMMIT" | sed 's/^/    /' | head -25
  fi
fi

$ok && echo "==> Done. Deployed $COMMIT ($TARGET)." || { echo "==> WARNING: health check did not return 200 — verify manually."; exit 1; }
