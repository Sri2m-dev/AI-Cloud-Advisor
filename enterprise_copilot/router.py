from __future__ import annotations

from time import perf_counter

INTENTS = (
    ("change", ("what breaks", "if i", "change impact")),
    ("financial", ("spend", "cost", "allocation", "savings", "budget")),
    ("dependency", ("depend", "uses", "connected", "relationship")),
    ("ownership", ("owner", "owns", "owned", "unowned")),
    ("classification", ("classif", "business unit", "cost center", "environment")),
    ("risk", ("risk", "critical", "exposure")),
    ("health", ("health", "incident", "operational")),
    ("inventory", ("inventory", "account", "application", "technology", "service")),
    ("search", ("find", "show", "list", "search")),
)


def route_intent(prompt: str):
    started = perf_counter()
    text = prompt.casefold()
    intent = next(
        (name for name, terms in INTENTS if any(term in text for term in terms)), "unknown"
    )
    return intent, (perf_counter() - started) * 1000
