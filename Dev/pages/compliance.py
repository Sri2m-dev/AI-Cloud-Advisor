from pathlib import Path
import sys

import streamlit as st

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shared.nav import render_sidebar, render_header_bar, require_role


if "role" not in st.session_state:
    st.switch_page("app.py")

require_role("CEO")
render_sidebar("Compliance")
render_header_bar()

st.title("🔒 Security & Compliance")

st.markdown("### 🌍 Data Protection")

st.success("✔ GDPR Compliant (EU Region)")
st.success("✔ Data encrypted in transit and at rest")
st.success("✔ Role-based access control implemented")

st.markdown("---")

st.markdown("### 🔐 AI Safety")

st.info("AI operates in controlled mode with no raw infrastructure data exposure")

st.markdown("---")

st.markdown("### 🏢 Architecture")

st.write("""
- Data stored securely in Supabase (EU region)
- No sensitive data shared externally
- All actions are logged and auditable
""")

st.markdown("---")

st.markdown("### 📜 Audit & Governance")

st.write("""
- All optimization actions are logged
- Role-based access ensures control
- Full traceability for compliance
""")
