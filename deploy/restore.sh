#!/usr/bin/env sh
# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 提供显式确认的数据库与附件恢复流程，避免误覆盖虚拟机现有业务数据。
set -eu

backup_dir="${1:-}"
if [ -z "$backup_dir" ] || [ ! -f "$backup_dir/database.dump" ] || [ ! -f "$backup_dir/storage.tar.gz" ]; then
  echo "Usage: RESTORE_CONFIRM=YES ./deploy/restore.sh backups/YYYYMMDD-HHMMSS"
  exit 1
fi
if [ "${RESTORE_CONFIRM:-NO}" != "YES" ]; then
  echo "Restore will replace the current database and attachments. Set RESTORE_CONFIRM=YES to continue."
  exit 1
fi

set -a
. ./.env
set +a

docker compose stop api worker beat
docker compose exec -T db pg_restore --clean --if-exists --no-owner -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" < "$backup_dir/database.dump"
docker compose run --rm -T api sh -c 'rm -rf /app/storage/* && tar xzf - -C /app/storage' < "$backup_dir/storage.tar.gz"
docker compose start api worker beat
echo "Restore completed from: $backup_dir"

