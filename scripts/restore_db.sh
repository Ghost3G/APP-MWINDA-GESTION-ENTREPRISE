#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: ./scripts/restore_db.sh <backup-file.sqlite3.gz>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_PATH="${ROOT_DIR}/db.sqlite3"
BACKUP_FILE="$1"

if [[ ! -f "${BACKUP_FILE}" ]]; then
  echo "Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

TMP_FILE="$(mktemp)"
gzip -dc "${BACKUP_FILE}" > "${TMP_FILE}"
mv "${TMP_FILE}" "${DB_PATH}"

echo "Database restored from: ${BACKUP_FILE}"
