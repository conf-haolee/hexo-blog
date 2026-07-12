#!/usr/bin/env sh
set -eu

DATA_DIR="${WORKBOARD_DATA_DIR:-./data}"
BACKUP_DIR="${WORKBOARD_BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/workboard-$STAMP.tar.gz" -C "$DATA_DIR" .
find "$BACKUP_DIR" -type f -name 'workboard-*.tar.gz' -mtime +30 -delete

