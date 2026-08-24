from __future__ import annotations

import re

POLICY_VERSION = "copilot-policy-v1"
ALLOWED_PERSONAS = frozenset(
    {"super_admin", "client_admin", "executive", "cio", "finance", "auditor", "operations"}
)
BLOCKED = {
    "mutation": re.compile(
        r"\b(delete|update|insert|approve|execute|decommission|shut down|suspend)\b", re.I
    ),
    "credentials": re.compile(r"\b(secret|password|credential|api key|token)\b", re.I),
    "raw_access": re.compile(r"\b(select\s+.+\s+from|raw sql|repository access)\b", re.I),
}


def evaluate_prompt(prompt: str, persona: str):
    if persona not in ALLOWED_PERSONAS:
        return False, "persona denied"
    for reason, pattern in BLOCKED.items():
        if pattern.search(prompt):
            return False, f"blocked {reason} request"
    return True, "read-only request allowed"
