#!/usr/bin/env bash
set -euo pipefail
umask 077

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
migration_file="${repo_root}/database/contracts/v1_customer_workflow/001_customer_workflow_postgres.sql"

: "${NEXORA_RECOVERY_PACKAGE:?set the verified encrypted package path}"
: "${NEXORA_BACKUP_KEY_FILE:?set the separately recovered backup-key file}"
: "${NEXORA_BACKUP_KEY_ID:?set the expected non-secret backup key ID}"
: "${NEXORA_RECOVERY_DATABASE:?set a new recovery database name}"
: "${NEXORA_RECOVERY_STORAGE_ROOT:?set a new recovery storage directory}"
: "${TARGET_PGHOST:?set the independent PostgreSQL recovery host}"
: "${TARGET_PGPORT:?set the independent PostgreSQL port}"
: "${TARGET_PGDATABASE:?set an existing admin database}"
: "${TARGET_PGUSER:?set the separately provisioned recovery administrator}"

python -m scripts.postgres_recovery_package verify \
  --source "${NEXORA_RECOVERY_PACKAGE}" \
  --key-file "${NEXORA_BACKUP_KEY_FILE}" \
  --key-id "${NEXORA_BACKUP_KEY_ID}" \
  --migration-file "${migration_file}"

python -m scripts.postgres_recovery_package restore \
  --source "${NEXORA_RECOVERY_PACKAGE}" \
  --key-file "${NEXORA_BACKUP_KEY_FILE}" \
  --key-id "${NEXORA_BACKUP_KEY_ID}" \
  --migration-file "${migration_file}" \
  --target-database "${NEXORA_RECOVERY_DATABASE}" \
  --storage-destination "${NEXORA_RECOVERY_STORAGE_ROOT}"
