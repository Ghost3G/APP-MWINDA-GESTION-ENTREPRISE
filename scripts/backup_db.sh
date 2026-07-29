#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ROOT_DIR}/backups"
STAMP="$(date +%Y%m%d_%H%M%S)"
DB_PATH="${ROOT_DIR}/db.sqlite3"

mkdir -p "${BACKUP_DIR}"

if [[ ! -f "${DB_PATH}" ]]; then
  echo "Database file not found: ${DB_PATH}"
  exit 1
fi

TARGET="${BACKUP_DIR}/db_${STAMP}.sqlite3"
cp "${DB_PATH}" "${TARGET}"
gzip -f "${TARGET}"

echo "Backup created: ${TARGET}.gz"
