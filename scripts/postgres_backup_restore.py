"""Compatibility entrypoint for the complete encrypted PostgreSQL package."""

from scripts.postgres_recovery_package import (
    DatabaseConfig,
    RecoveryPackageError,
    create_backup_package,
    main,
    restore_backup_package,
    verify_backup_package,
)

__all__ = [
    "DatabaseConfig",
    "RecoveryPackageError",
    "create_backup_package",
    "restore_backup_package",
    "verify_backup_package",
]


if __name__ == "__main__":
    raise SystemExit(main())
