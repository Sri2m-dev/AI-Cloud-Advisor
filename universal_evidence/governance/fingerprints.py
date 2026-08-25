"""Deterministic governance identity helpers."""

import hashlib


def fingerprint(*values: object) -> str:
    return hashlib.sha256(repr(values).encode("utf-8")).hexdigest()
