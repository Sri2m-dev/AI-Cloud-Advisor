from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from services.comparison_engine import compare_instance
from services.roi_engine import calculate_roi
from services.migration_cost_engine import estimate_migration_cost, calculate_payback
from services.suitability_engine import calculate_suitability, interpret_score
from services.risk_engine import calculate_risk, interpret_risk
from services.complexity_engine import calculate_complexity, interpret_complexity
from services.decision_engine import generate_decision
from shared.nav import render_sidebar, render_header_bar

render_sidebar("Multi-Cloud Advisor")
render_header_bar()

st.title("🌐 Multi-Cloud Migration Advisor")

resource = {
    "utilization": 25,
    "cost": 1200,
    "dependency": "medium",
    "data_size": "medium",
    "downtime": "low",
    "architecture": "monolith",
    "integrations": 3
}

score = calculate_suitability(resource)
interpretation = interpret_score(score)
risk_score = calculate_risk(resource)
risk_level = interpret_risk(risk_score)
complexity_score = calculate_complexity(resource)
complexity_level = interpret_complexity(complexity_score)

st.subheader("🧠 Migration Suitability Score")
st.metric("Score", f"{score}/100")
st.info(interpretation)

col1, col2 = st.columns(2)
col1.metric("Suitability Score", f"{score}/100")
col2.metric("Recommendation", interpretation)

st.subheader("⚠️ Migration Risk Analysis")
risk_col1, risk_col2 = st.columns(2)
risk_col1.metric("Risk Level", risk_level)
risk_col2.metric("Complexity", complexity_level)

st.info("""
🤖 AI Insight:
- Moderate dependency and downtime sensitivity increase migration risk  
- Monolithic architecture increases complexity  
- Recommended approach: phased migration
""")

instance = st.selectbox("Select Instance", ["m5.large"])
results = compare_instance(instance)

st.subheader("🔍 Comparison Results")

if results:
    for r in results:
        roi = calculate_roi(1200, r["cost"])
        migration = estimate_migration_cost(instance)
        payback = calculate_payback(migration["total"], r["savings"])

        st.markdown(f"""
### {r['provider']}

- Instance: {r['instance']}
- Cost: ${r['cost']}
- Savings: ${r['savings']}
- Performance Gain: +{r['performance_gain']}%

💸 Migration Cost: ${migration['total']}
⏳ Payback Period: {payback} months
""")

        with st.expander("🔍 Migration Cost Breakdown"):
            for k, v in migration["breakdown"].items():
                st.write(f"{k}: ${v}")

    best = max(results, key=lambda x: x["savings"])
    best_migration = estimate_migration_cost(instance)
    best_payback = calculate_payback(best_migration["total"], best["savings"])
    decision = generate_decision(
        best_option=best,
        roi=best_payback,
        suitability=score,
        risk=risk_level,
        complexity=complexity_level
    )

    st.markdown("## 🤖 AI Migration Decision")
    risk_text = decision.get("risk", "Unknown Risk")
    target_cloud = decision.get("target_cloud", "GCP")
    recommendation_text = decision.get("recommendation")
    if not recommendation_text:
        if "High" in risk_text:
            recommendation_text = f"🚫 Recommendation: Do NOT migrate to {target_cloud}"
        elif "Medium" in risk_text:
            recommendation_text = f"⚠️ Recommendation: Move to {target_cloud} (Phased Migration)"
        else:
            recommendation_text = f"✅ Recommendation: Move to {target_cloud}"

    reason_text = decision.get("reason", "Migration decision generated from current risk and suitability analysis")
    savings_note = decision.get("savings_note", f"💰 Potential Savings: ${decision.get('savings', 0)}")
    approach_text = decision.get("approach", "Standard migration rollout")
    final_verdict = decision.get("final", "Decision pending")

    decision_message = f"""
### {recommendation_text}

**Reason:**  
{reason_text}

{savings_note}  
⚠️ Risk: {risk_text}  
⚙️ Approach: {approach_text}
"""

    if "Not Recommended" in final_verdict:
        st.warning(decision_message)
    elif "phased migration" in final_verdict:
        st.info(decision_message)
    else:
        st.success(decision_message)

    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("💰 Savings", f"${decision['savings']}")
    summary_col2.metric("⏳ Payback", f"{decision['payback']} months")
    summary_col3.metric("⚠️ Risk", decision['risk'])

    if "High" in decision["risk"]:
        st.info("💡 Suggested Action: Optimize within current cloud before considering migration")
        st.info(f"""
🤖 AI Explanation:
- {decision['target_cloud']} may offer savings, but the migration risk is currently too high  
- Reduce dependency complexity and operational risk before re-evaluating  

Recommendation: Optimize the current environment first
""")
    elif "Medium" in decision["risk"]:
        st.info(f"""
🤖 AI Explanation:
- {decision['target_cloud']} offers a favorable cost-performance ratio  
- Risk is manageable with a gradual workload shift  

Recommendation: Proceed in phases
""")
    else:
        st.info(f"""
🤖 AI Explanation:
- {decision['target_cloud']} offers a strong cost-performance advantage  
- Migration risk is low and suitable for execution  

Recommendation: Proceed with migration
""")
else:
    st.warning("No comparison results available for the selected instance.")
