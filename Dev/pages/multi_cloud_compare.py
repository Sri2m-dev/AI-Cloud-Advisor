from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from services.cloud_mapping import compare_clouds
from shared.nav import render_sidebar, render_header_bar

render_sidebar("Multi-Cloud Compare")
render_header_bar()

st.title("🌐 Multi-Cloud Optimization")

resource = {
    "service": "EC2",
    "instance": st.selectbox("Select Resource", ["m5.large"]),
    "utilization": 25,
}

st.caption(
    f"Current workload → Service: {resource['service']} | Instance: {resource['instance']} | Utilization: {resource['utilization']}%"
)

result = compare_clouds(resource)

if result:
    if resource["utilization"] < 30:
        st.warning("Low utilization detected — this workload is a strong candidate for optimization or migration.")

    for r in result:
        st.info(
            f"{r['provider']} ({r['instance']}) → Save ${r['savings']} | Performance: {r['performance']}%"
        )

    best = max(result, key=lambda x: x["savings"])
    st.success(
        f"💡 AI Recommendation: Move to {best['provider']} to save ${best['savings']} with better performance"
    )
else:
    st.warning("No comparison data available for the selected resource.")
