"""Deterministic identities for PUE-010 shadow artifacts."""

import hashlib


def fingerprint(*values: object) -> str:
    return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()
