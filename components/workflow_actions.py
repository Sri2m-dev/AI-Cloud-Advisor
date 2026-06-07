"""Workflow Actions Component"""
import streamlit as st

WORKFLOW_ACTIONS = [
    "Approve",
    "Reject",
    "Assign",
    "Escalate",
    "Snooze",
    "Complete",
]


def render_workflow_actions(on_action, actions=WORKFLOW_ACTIONS):
    """Render workflow action buttons.

    on_action: Callback function(action_name)
    actions: List of action names (str), defaults to all workflow actions
    """
    cols = st.columns(len(actions))
    for col, action in zip(cols, actions):
        if col.button(action):
            on_action(action)

