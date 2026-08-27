"""Deterministic PUE activation control-plane identities."""

import hashlib


def fingerprint(*values: object) -> str:
    return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()
