from functools import wraps

def with_error_handling(func):
	@wraps(func)
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except Exception as e:
			logging.exception(f"Error in {func.__name__}: {str(e)}")
			return {
				"success": False,
				"error": str(e),
				"data": None
			}
	return wrapper
"""
Global error handler for consistent exception reporting and logging.
"""

import streamlit as st
import traceback
import logging
import functools
import time

class ValidationError(Exception):
	pass

class PermissionError(Exception):
	pass

def handle_error(e, user_message=None, log_traceback=True, extra_context=None):
	"""
	Handles exceptions in a consistent way across the app.
	- Displays a user-friendly error message in Streamlit
	- Logs the traceback for debugging
	"""
	# Structured log entry
	log_entry = {
		"type": type(e).__name__,
		"message": str(e),
		"context": extra_context or {},
		"traceback": traceback.format_exc() if log_traceback else None
	}
	logging.error(log_entry)

	# User-safe error display
	if isinstance(e, ValidationError):
		st.warning(user_message or "Validation error. Please check your input.")
	elif isinstance(e, PermissionError):
		st.error(user_message or "You do not have permission to perform this action.")
	else:
		st.error(user_message or "An unexpected error occurred. Please contact support.")
	if log_traceback:
		st.expander("Show error details").write(log_entry["traceback"])

