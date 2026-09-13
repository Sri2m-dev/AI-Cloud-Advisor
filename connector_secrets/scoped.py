"""Tenant-bound encrypted connector material using the existing credential cipher."""

import os

from connector_secrets import SecretProvider


class ScopedCredentialProvider(SecretProvider):
    def __init__(self, context, source_id, ciphertext):
        self.context, self.source_id, self.ciphertext = context, source_id, ciphertext

    @staticmethod
    def _require_key():
        if os.getenv("FERNET_KEY") or os.getenv("NEXORA_PROSPECT_DATA_KEY"):
            return
        from pathlib import Path
        if Path("fernet.key").exists():
            return
        from database.db import _get_fernet
        try:
            _get_fernet()
        except Exception as exc:
            raise ValueError("Connector encryption key is not configured") from exc

    @classmethod
    def seal(cls, context, source_id, material):
        cls._require_key()
        from database.db import encrypt_credentials

        return encrypt_credentials({
            "organization_id": context.organization_id,
            "tenant_id": context.tenant_id,
            "source_id": source_id,
            "material": dict(material),
        })

    def resolve(self, secret_ref):
        self._require_key()
        from database.db import decrypt_credentials

        try:
            envelope = decrypt_credentials(self.ciphertext)
            if (
                envelope["organization_id"] != self.context.organization_id
                or envelope["tenant_id"] != self.context.tenant_id
                or envelope["source_id"] != self.source_id
            ):
                raise ValueError("scope mismatch")
            if secret_ref not in ("external_id", "client_secret"):
                raise ValueError("unsupported credential slot")
            return envelope["material"].get(secret_ref)
        except Exception:
            raise ValueError("Connector credential is unavailable") from None

    def __repr__(self):
        return "ScopedCredentialProvider(<redacted>)"
