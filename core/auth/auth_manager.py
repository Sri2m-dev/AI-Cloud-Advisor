import streamlit as st
from services.supabase_client import supabase
from auth.role_constants import normalize_role


def login_user(email, password):
	"""Authenticate user and set session state."""
	response = supabase.auth.sign_in_with_password({"email": email, "password": password})
	auth_user = response.user
	session = response.session
	if not auth_user:
		return None
	profile_response = (
		supabase.table("users")
		.select("*")
		.eq("email", auth_user.email)
		# .maybe_single() removed per security requirements
		.execute()
	)
	# 'if not profile:' removed per security requirements
	if not profile_response.data:
		st.error("No RBAC profile assigned to this user.")
		st.stop()
	# Always return/store a single profile object
	profile = profile_response.data[0] if isinstance(profile_response.data, list) and profile_response.data else profile_response.data
	st.session_state.profile = profile
	st.session_state.authenticated = True
	st.session_state.user = auth_user
	st.session_state.session = session
	st.session_state.user_id = auth_user.id
	st.session_state.email = auth_user.email
	st.session_state.role_display = profile.get("role")
	st.session_state.role = normalize_role(profile.get("role"))
	st.session_state.tenant = profile.get("tenant_id")
	st.session_state.permissions = profile.get("permissions", [])
	return auth_user

def logout_user():
	"""Clear session state and log out user."""
	for key in ["authenticated", "user", "session", "user_id", "email", "role", "org_id", "tenant", "permissions"]:
		if key in st.session_state:
			del st.session_state[key]
	supabase.auth.sign_out()

