import os
import sys
import streamlit as st
from shared.session import init_session
from shared.styles import configure_page

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

configure_page(page_title="Leadership Dashboard | AI Cloud Advisor", page_icon=":trophy:")

init_session()

from shared.auth import require_role

require_role([
    "executive",
    "super_admin",
])

from components.layout import render_page_header, render_section
from services.leadership_service import (
    get_financial_overview,
    get_executive_metrics,
    get_strategic_initiatives,
)
from components.tables import data_table

render_page_header("Leadership Dashboard", "Executive insights and financial KPIs")

org_id = st.session_state.get("organization_id")

render_section("Financial Overview")
fin_overview = get_financial_overview(org_id)
if fin_overview and fin_overview.get("success"):
    data_table(fin_overview.get("data"))
else:
    st.write("No financial data available.")

render_section("Executive Metrics")
exec_metrics = get_executive_metrics(org_id)
if exec_metrics and exec_metrics.get("success"):
    data_table(exec_metrics.get("data"))
else:
    st.write("No executive metrics available.")

render_section("Strategic Initiatives")
strat_resp = get_strategic_initiatives(org_id)
if strat_resp and strat_resp.get("success"):
    data_table(strat_resp.get("data"))
else:
    st.write("No strategic initiatives found.")
