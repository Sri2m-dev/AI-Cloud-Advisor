# Entrypoint for AI Cloud Advisor: Login Page

# --- ENTERPRISE LOGIN PAGE: FULLY CENTERED, NO SIDEBAR, CARD UX ---
import streamlit as st
from streamlit import switch_page
from core.errors.error_handler import handle_error
from core.logging.audit_logger import AuditLogger
from core.auth import login_user
from auth.role_constants import normalize_role

st.set_page_config(
	page_title="AI Cloud Advisor",
	layout="wide",
	initial_sidebar_state="collapsed"
)

# Fully hide sidebar and toggle
st.markdown("""
<style>
[data-testid="stSidebar"] {
	display: none;
}
[data-testid="collapsedControl"] {
	display: none;
}
</style>
""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
	st.session_state["authenticated"] = False
if "user" not in st.session_state:
	st.session_state.user = None
if "role" not in st.session_state:
	st.session_state.role = None
if "show_reset" not in st.session_state:
	st.session_state.show_reset = False
if "show_signup" not in st.session_state:
	st.session_state.show_signup = False

# DEV BYPASS: temporarily skip login during development
st.session_state["authenticated"] = True
st.session_state["user"] = {
	"name": "Srikanth",
	"role": "SuperAdmin",
	"email": "srikanth@example.com"
}
st.session_state["role_display"] = "SuperAdmin"
st.session_state["role"] = normalize_role("SuperAdmin")

left, center, right = st.columns([2,3,2])
with center:
	with st.container(border=True):
		st.markdown("# 🔐 AI Cloud Advisor Login")
		st.markdown("### Enterprise Cloud Governance Platform")
		st.write("")

		email = st.text_input("Email")
		password = st.text_input("Password", type="password")
		st.write("")

		col1, col2 = st.columns(2)
		with col1:
			login_btn = st.button("Login", use_container_width=True)
		with col2:
			signup_btn = st.button("Sign Up", use_container_width=True)

		st.write("")
		forgot = st.button("Forgot Password?", use_container_width=True)

		# --- Login logic ---
		if login_btn:
			try:
				user = login_user(email.lower().strip(), password)
				if not user:
					st.error("Authentication failed.")
					st.stop()
				st.session_state["authenticated"] = True
				st.session_state["user"] = user
				st.success("Login successful")
				switch_page("pages/executive_dashboard.py")
			except Exception as e:
				handle_error(e, user_message="Login failed")

		# --- Registration (Sign Up) ---
		if signup_btn or st.session_state.show_signup:
			st.session_state.show_signup = True
			st.subheader("Sign Up for AI Cloud Advisor")
			with st.form("signup_form"):
				signup_email = st.text_input("Email", key="signup_email")
				signup_password = st.text_input("Password", type="password", key="signup_password")
				signup_submit = st.form_submit_button("Sign Up")
				if signup_submit:
					if not signup_email or not signup_password:
						st.error("Please enter both email and password.")
					else:
						st.success("Registration successful! (placeholder)")
						st.session_state.show_signup = False

		# --- Forgot Password ---
		if forgot or st.session_state.show_reset:
			st.session_state.show_reset = True
			st.subheader("Reset Your Password")
			with st.form("reset_form"):
				reset_email = st.text_input("Email", key="reset_email")
				reset_submit = st.form_submit_button("Send Reset Link")
				if reset_submit:
					if not reset_email:
						st.error("Please enter your email.")
					else:
						st.success("Password reset link sent! (placeholder)")
						st.session_state.show_reset = False

	if st.session_state.user:
		user_email = None
		if isinstance(st.session_state.user, dict):
			user_email = st.session_state.user.get("email")
		else:
			user_email = getattr(st.session_state.user, "email", None)
		st.info(f"Logged in as: {user_email or 'unknown user'} (Role: {st.session_state.role})")
		st.write("You can now access the platform.")

