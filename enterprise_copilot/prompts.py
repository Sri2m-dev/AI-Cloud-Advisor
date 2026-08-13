PROMPTS = {
    "grounded-answer-v1": (
        "Explain only the supplied governed context. Cite every factual statement. "
        "Preserve UNKNOWN values. Never recommend, approve, mutate, or execute."
    )
}


def prompt(name="grounded-answer-v1"):
    return PROMPTS[name]
