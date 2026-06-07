import streamlit as st

def ApprovalCard(title: str, status: str, approver: str, submitted_at: str, on_approve=None, on_reject=None, user_role=None):
    """
    Display an approval card with approve/reject buttons, hidden for CEO.
    """
    st.write(f"**{title}**")
    st.write(f"Status: {status}")
    st.write(f"Approver: {approver}")
    st.write(f"Submitted: {submitted_at}")
    if user_role and str(user_role).lower() == "ceo":
        st.info("Read-only: CEO cannot approve or reject.")
        return
    col1, col2 = st.columns(2)
    if on_approve and col1.button("Approve", key=f"approve_{title}"):
        on_approve()
    if on_reject and col2.button("Reject", key=f"reject_{title}"):
        on_reject()

