#!/usr/bin/env sh
# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 为单机虚拟机提供可定时执行的数据库与附件一致性备份入口。
set -eu

backup_root="${BACKUP_ROOT:-./backups}"
timestamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_root/$timestamp"

# CHANGE [2026-08-30 12:58 +08:00] [WH400]: 从未提交的环境文件读取数据库名，避免脚本依赖调用者手工导出变量。
set -a
. ./.env
set +a

docker compose exec -T db pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -Fc > "$backup_root/$timestamp/database.dump"
docker compose exec -T api tar czf - -C /app/storage . > "$backup_root/$timestamp/storage.tar.gz"

find "$backup_root" -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf -- {} +
echo "Backup completed: $backup_root/$timestamp"

