"""Centralized UI copy for transient toast notifications."""


TOAST_LOGIN_WELCOME = ("Welcome back!", "👋")
TOAST_RECOMMENDATION_ACCEPTED = ("Recommendation accepted.", "✅")
TOAST_RECOMMENDATION_SNOOZED = ("Recommendation snoozed.", "⏸️")
TOAST_RECOMMENDATION_COMPLETED = ("Recommendation marked complete! 🎉", "✅")
TOAST_RECOMMENDATION_DISMISSED = ("Recommendation dismissed.", "🗑️")
TOAST_OPT_WORKFLOW_SAVED = ("10 optimization recommendations saved to your workflow.", "💾")
TOAST_OPT_DETAILS_SAVED = ("Details saved.", "💾")
TOAST_OPT_ACCEPTED = ("Opportunity accepted.", "✅")
TOAST_OPT_COMPLETED = ("Opportunity marked complete! 🎉", "✅")
TOAST_OPT_SNOOZED = ("Opportunity snoozed.", "⏸️")


def toast_ai_recommendations_added(count: int) -> tuple[str, str]:
    return (f"Added {count} AI recommendation(s) to your workflow.", "🤖")


def toast_recommendations_added(count: int) -> tuple[str, str]:
    return (f"Added {count} recommendation(s).", "🤖")

