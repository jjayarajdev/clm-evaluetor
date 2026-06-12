# AWS Rollback Runbook

Last verified: **2026-05-11**

This document is the answer to "how do we revert AWS to a known-good state?"
It assumes the safety kit captured on 2026-05-11 is intact (see below).

---

## Current AWS production state (as of 2026-05-11)

| Item | Value |
|------|-------|
| Host | `ec2-user@52.21.204.211` |
| SSH | `ssh -i ~/.ssh/clm-demo-key.pem ec2-user@52.21.204.211` |
| Deploy directory | `/home/ec2-user/clm/deploy` |
| Backend image | `sha256:d7eebbd6e610bc67f7d7911953d20d6056511fd71f006429135430f5be2a906b` |
| Frontend image | `sha256:d245a93d1e55ad9ce9cb682aa385326cc74d067ce9e39bf9f1b36574dc3dad24` |
| Postgres image | `sha256:15283455b75304c90f51bf16b42c272a25fb52807945dc24830ec88e63cd896d` |
| Backend / frontend last started | 2026-05-04 (image built 2026-05-04T09:00:41 UTC) |
| Postgres uptime | ~2 months |
| Closest matching git commit | `9b3c1b7` (release branch, before today's merge `7faa22e`) |
| DB `alembic_version` | `cp01` + `hl01_add_highlight_rects` (two rows — fixed 2026-05-11, see below) |

### Caveats / oddities

1. **`~/clm` on AWS is NOT a git checkout.** Deploys happen by file copy, not `git pull`. There is no `.git` directory anywhere on the host. The tag `aws-stable-2026-05-11` is the closest *git* representation, not a literal mirror.
2. **`cp01_contract_industry_profile.py`** existed in the deployed container *before* it was committed to git. It's a manually-added file that was already on the AWS box from May 4. Today's commit `40aed66` brought it into git history.
3. **Orphaned schema effects.** The DB has schema changes from migrations that aren't in the deployed container's chain (`ct01_contract_type_to_varchar`, `ip01_add_industry_profiles`, etc.). Their effects are present (e.g. `contract_type` is VARCHAR(100), `industry_profiles` table exists) but the files are missing from the deployed `/app/alembic/versions/`. Disaster recovery from a clean DB would diverge — eventually we should generate a single ground-zero migration that creates the full current schema and retire the old chains.
4. **Dead `contracttype` enum** still exists in `pg_type` even though `ct01` was supposed to drop it (partial application). Harmless — the column is VARCHAR now. Cleanup: `DROP TYPE IF EXISTS contracttype;` whenever convenient.

### alembic_version fix history

| Date | Before | After | Why |
|------|--------|-------|-----|
| 2026-05-11 | single row `ct01_contract_type_to_varchar` (revision not findable in container) | two rows `cp01`, `hl01_add_highlight_rects` | `alembic current` failed → `alembic upgrade head` would have failed on next deploy. Stamped to the two heads that actually exist in the container chain. No schema changes; only metadata table updated. Pre-fix dump: `clm-pre-alembic-fix-20260511-081744.dump`. |

---

## Safety artifacts captured on AWS (2026-05-11)

All under `/home/ec2-user/clm-backups/` on the EC2 box:

```
STATE-20260511-055520.txt                            # human-readable state record
clm-pre-multidomain-20260511-055520.dump             # pg_dump pre-fix, 8.4MB
clm-pre-alembic-fix-20260511-081744.dump             # pg_dump immediately before the alembic_version fix, 8.4MB
```

Docker images tagged on the box (won't be pruned by `docker image prune`):

```
deploy-backend:aws-stable-2026-05-11
deploy-frontend:aws-stable-2026-05-11
```

Git tag (in origin):

```
aws-stable-2026-05-11   # annotated tag on commit 9b3c1b7
```

---

## Rollback procedure

There are three layers to roll back. Use whichever is required by the symptom.

### Layer 1 — Container rollback (fastest, no rebuild)

If a bad deploy just broke the running app and the DB is fine, just point compose at the tagged images.

```bash
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@52.21.204.211
cd ~/clm/deploy

# Stop the bad containers (keeps volumes / DB intact)
docker-compose -f docker-compose.prod.yml stop backend frontend

# Re-tag the saved snapshots as the names compose expects, then re-up
docker tag deploy-backend:aws-stable-2026-05-11  deploy-backend:latest
docker tag deploy-frontend:aws-stable-2026-05-11 deploy-frontend:latest

# Recreate from the tagged images without rebuilding
docker-compose -f docker-compose.prod.yml up -d --no-build backend frontend

# Verify
docker ps
curl -s http://localhost/api/health | head -5
```

If `--no-build` doesn't work with the current compose file (it references a `build:` block), edit the file to reference `image: deploy-backend:aws-stable-2026-05-11` temporarily, then `up -d`.

### Layer 2 — DB rollback (only if data is corrupted)

**Only do this if container rollback isn't enough.** Restoring overwrites the DB.

```bash
ssh -i ~/.ssh/clm-demo-key.pem ec2-user@52.21.204.211

# Stop the app so nothing writes while restoring
cd ~/clm/deploy
docker-compose -f docker-compose.prod.yml stop backend

# Optional safety net: dump CURRENT DB first in case the rollback is the mistake
STAMP=$(date +%Y%m%d-%H%M%S)
docker exec deploy-postgres-1 pg_dump -U clm -d clm -Fc > ~/clm-backups/clm-before-rollback-${STAMP}.dump

# Restore the 2026-05-11 snapshot
# (-c drops and recreates objects; --if-exists avoids errors when objects don't exist yet)
docker exec -i deploy-postgres-1 pg_restore -U clm -d clm --clean --if-exists --no-owner \
  < ~/clm-backups/clm-pre-multidomain-20260511-055520.dump

# Bring the backend back up
docker-compose -f docker-compose.prod.yml start backend

# Verify
docker exec deploy-postgres-1 psql -U clm -d clm -c "SELECT version_num FROM alembic_version;"
docker exec deploy-postgres-1 psql -U clm -d clm -c "SELECT count(*) FROM contracts;"
```

### Layer 3 — Source rollback (rare — only if we need to rebuild the image)

Use this if Layer 1's saved images are corrupted/lost AND we need to recreate the May-4 build from source.

```bash
# On a local dev machine
git fetch origin
git checkout aws-stable-2026-05-11           # detached HEAD at 9b3c1b7

# Manually re-add the out-of-tree file that was on AWS but not in git at the time
# (it's now in main history at 40aed66 — easy to grab)
git show 40aed66:backend/alembic/versions/cp01_contract_industry_profile.py \
  > backend/alembic/versions/cp01_contract_industry_profile.py

# Then rsync / scp to AWS as before and rebuild:
cd ~/clm/deploy
docker-compose -f docker-compose.prod.yml build --no-cache backend frontend
docker-compose -f docker-compose.prod.yml up -d backend frontend
```

---

## Before any future deploy — checklist

1. **Take a fresh DB dump** with the same pattern:
   ```bash
   STAMP=$(date +%Y%m%d-%H%M%S)
   ssh ec2-user@52.21.204.211 \
     "docker exec deploy-postgres-1 pg_dump -U clm -d clm -Fc \
      > ~/clm-backups/clm-pre-deploy-${STAMP}.dump"
   ```
2. **Tag the current images** so the previous-stable state is preserved:
   ```bash
   ssh ec2-user@52.21.204.211 '
     STAMP=$(date +%Y%m%d-%H%M%S)
     docker tag $(docker inspect deploy-backend-1  --format "{{.Image}}") deploy-backend:aws-stable-${STAMP}
     docker tag $(docker inspect deploy-frontend-1 --format "{{.Image}}") deploy-frontend:aws-stable-${STAMP}
   '
   ```
3. **Update this file** with the new image SHAs + dump filename.
4. **Apply migrations explicitly** rather than relying on container startup:
   ```bash
   docker exec deploy-backend-1 sh -c "cd /app && alembic upgrade head"
   ```
   Watch for errors. If `alembic_version` is `ct01_contract_type_to_varchar` (missing file), this will fail until that pre-existing inconsistency is resolved separately.

---

## Verifying a rollback actually worked

```bash
# App health
curl -sS https://your-domain/api/health    # adjust if you have a DNS name
ssh ec2-user@52.21.204.211 'docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"'

# Smoke test login
ssh ec2-user@52.21.204.211 'curl -s http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"superadmin\",\"password\":\"admin123\"}" | head -c 200'

# Read a contract list (auth required — replace TOKEN)
ssh ec2-user@52.21.204.211 \
  "curl -s http://localhost/api/contracts -H \"Authorization: Bearer TOKEN\" | head -c 500"
```

If any of those fail, the rollback didn't fully take and you may need to escalate to Layer 2 or Layer 3.
