# AlphaPilot Production Deployment

## Required GitHub Secrets
- `SERVER_HOST`
- `SERVER_USER`
- `SSH_PRIVATE_KEY`
- `PROD_ENV_CONTENT` (full `.env.prod` content)

## Optional Environment Variables
- `APP_DIR` (default: `/opt/alphapilot`)
- `GIT_BRANCH` (default: `main`)
- `RETENTION_DAYS` (default: `14`)

## First-time Server Setup
1. Install Docker Engine and Docker Compose plugin.
2. Ensure the deploy user can run Docker commands.
3. Open ports `80` and `22`.
4. Set DNS record to server IP.

## Runtime Paths
- `runtime/checkpoints` - SQLite DB and graph checkpoints
- `runtime/backups` - automated backup artifacts
- `runtime/data` - profile and memory artifacts
- `runtime/rag_data` - vector DB files
- `runtime/hf_cache` - model cache data

## Security Baseline
- Set strong `JWT_SECRET` in `.env.prod`.
- Restrict `ALLOWED_ORIGINS` to your production domain.
- Keep `SSH_PRIVATE_KEY` as deploy-only key with minimal host privileges.
- Rotate secrets periodically.

## Backup and Retention
- GitHub Actions `Nightly Backup` runs `deploy/backup.sh` daily.
- Default retention is 14 days (`RETENTION_DAYS`).
- Backups include SQLite DB, profile data, and RAG artifacts.

## Health Validation
After each deployment:

```bash
curl -f http://localhost/health
docker compose -f deploy/docker-compose.prod.yml ps
```
