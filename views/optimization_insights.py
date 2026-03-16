from datetime import date

import pandas as pd
import streamlit as st

from database.db import (
    can_manage_recommendation,
    list_recommendations,
    save_recommendation,
    update_recommendation_details,
    update_recommendation_status,
)
from services.optimization_engine import recommend_ri_purchase_timing
from views.ui_helpers import render_empty_state, show_toast
from views.ui_messages import (
    TOAST_OPT_ACCEPTED,
    TOAST_OPT_COMPLETED,
    TOAST_OPT_DETAILS_SAVED,
    TOAST_OPT_SNOOZED,
    TOAST_OPT_WORKFLOW_SAVED,
)


def _seed_optimization_recommendations(username):
    recommendations = [
        {
            "category": "rightsizing",
            "title": "Rightsize EC2 compute cluster",
            "description": "Several EC2 instances are consistently underutilized and can be moved to a smaller instance family.",
            "resource": "aws-prod:EC2",
            "estimated_savings": 4200,
            "priority": "high",
            "confidence_score": 0.9,
            "rationale": "Consistent under-utilization makes this a strong candidate for near-term savings without waiting for a new billing cycle.",
            "effort_level": "medium",
            "action_steps": [
                "Validate CPU and memory headroom for the target workloads.",
                "Select the next smaller instance class for each low-risk node.",
                "Resize in a maintenance window and verify performance after deployment.",
            ],
        },
        {
            "category": "spot_instances",
            "title": "Migrate fault-tolerant workloads to Spot Instances",
            "description": "EC2 Spot Instances provide up to 90% discount vs on-demand pricing. Suitable for stateless, fault-tolerant applications like batch processing, testing, and distributed analytics.",
            "resource": "aws-prod:EC2-Spot",
            "estimated_savings": 6800,
            "priority": "high",
            "confidence_score": 0.85,
            "rationale": "Estimated 60% of your EC2 workloads can be converted to Spot. Conservative 70% discount yields significant annual savings. Combine with capacity diversification across instance types for reliability.",
            "effort_level": "high",
            "action_steps": [
                "Identify fault-tolerant workloads (CI/CD, batch jobs, analytics, big data processing).",
                "Define instance type diversification strategy (3-5 types) to handle interruptions.",
                "Implement auto-scaling groups with mixed instance policy.",
                "Configure instance interruption handling (2-min warning hook).",
                "Monitor interruption rates and cost savings realized.",
            ],
        },
        {
            "category": "commitments",
            "title": "Optimize Savings Plans and RI utilization",
            "description": "Existing reserved capacity is underutilized (65% average). Rightsizing or consolidating commitments can recover wasted spend.",
            "resource": "aws-prod:Commitments",
            "estimated_savings": 3400,
            "priority": "high",
            "confidence_score": 0.88,
            "rationale": "Commitment utilization tracking shows $280/month unused capacity. This is due to instance oversizing and misaligned commitment terms. No additional purchase required—optimization only.",
            "effort_level": "low",
            "action_steps": [
                "Review current Savings Plans and Reserved Instance inventory in AWS.",
                "Compare purchased commitment hours vs. actual usage by instance family.",
                "Consolidate underutilized commitments or reallocate to popular instance types.",
                "Set up CloudWatch cost anomaly alerts to track commitment waste.",
                "Monitor utilization quarterly and adjust terms based on usage patterns.",
            ],
        },
        {
            "category": "database",
            "title": "Rightsize RDS instances",
            "description": "RDS CPU and memory utilization suggest the database tier is oversized for current demand.",
            "resource": "aws-prod:RDS",
            "estimated_savings": 2100,
            "priority": "high",
            "confidence_score": 0.84,
            "rationale": "Database sizing signals are stable enough that a controlled rightsize review is likely to return savings.",
            "effort_level": "medium",
            "action_steps": [
                "Review recent utilization, storage growth, and connection peaks.",
                "Select a smaller instance tier with rollback criteria defined.",
                "Apply the resize during a maintenance window and confirm service health.",
            ],
        },
        {
            "category": "scheduling",
            "title": "Implement scheduled stop/start for dev and non-prod EC2",
            "description": "Development, test, and batch workloads are active only during business hours but running 24/7. Automatic scheduling can reduce cost by 60-75% for these resources.",
            "resource": "aws-prod:EC2-Scheduling",
            "estimated_savings": 2800,
            "priority": "high",
            "confidence_score": 0.82,
            "rationale": "Dev/test environments typically run 8 hours/day (business hours). ~25% of EC2 fleet is non-production. Automated stop/start via EventBridge + Systems Manager requires minimal engineering.",
            "effort_level": "medium",
            "action_steps": [
                "Tag all development and test EC2 instances with 'environment=dev' and 'schedule=business-hours'.",
                "Create EventBridge rules to stop instances at 6 PM and start at 8 AM (adjust to your timezone).",
                "Use AWS Systems Manager or Lambda for orchestration.",
                "Test scheduled start/stop on 2-3 instances before full rollout.",
                "Monitor first 2 weeks for any service interruptions or missed schedules.",
            ],
        },
        {
            "category": "storage",
            "title": "Remove unattached EBS volumes",
            "description": "Unused EBS volumes are accruing storage charges with no active attachment history.",
            "resource": "aws-dev:EBS",
            "estimated_savings": 800,
            "priority": "medium",
            "confidence_score": 0.94,
            "rationale": "Detached storage with no recent attachment history is one of the clearest low-risk cleanup opportunities.",
            "effort_level": "low",
            "action_steps": [
                "Confirm the volumes are detached and not part of a pending recovery workflow.",
                "Snapshot any data that must be retained before deletion.",
                "Delete the orphaned volumes and monitor the next billing cycle for the reduction.",
            ],
        },
        {
            "category": "lifecycle",
            "title": "Move cold S3 data to infrequent access",
            "description": "Older S3 objects are good candidates for lifecycle transitions to lower-cost storage classes.",
            "resource": "aws-analytics:S3",
            "estimated_savings": 1200,
            "priority": "medium",
            "confidence_score": 0.82,
            "rationale": "Object age and access patterns suggest lifecycle automation will reduce spend with limited operational risk.",
            "effort_level": "low",
            "action_steps": [
                "Identify buckets with old objects and low read frequency.",
                "Define lifecycle transitions that match retention and retrieval needs.",
                "Roll out the policy and validate storage-class mix over the next week.",
            ],
        },
        {
            "category": "monitoring",
            "title": "Enable cost anomaly alerting and budgets",
            "description": "Set up real-time anomaly detection and budget threshold alerts to catch unexpected cost increases before they impact the monthly bill.",
            "resource": "aws-shared:Monitoring",
            "estimated_savings": 0,
            "priority": "high",
            "confidence_score": 0.92,
            "rationale": "Proactive monitoring prevents surprises and enables quick response to cost spikes. Most spikes go unnoticed until end-of-month billing. Early detection can save thousands.",
            "effort_level": "low",
            "action_steps": [
                "Create AWS Budget with monthly limit set to 110% of historical average.",
                "Configure Budget alerts at 70%, 85%, and 100% thresholds.",
                "Enable AWS Cost Anomaly Detection in Cost Anomaly Detector service.",
                "Subscribe SNS topic to receive email alerts for both budgets and anomalies.",
                "Test alert delivery with a dummy threshold.",
            ],
        },
        {
            "category": "network",
            "title": "Reduce cross-region and data egress costs",
            "description": "Data Transfer charges are the most commonly overlooked cost driver. Cross-region traffic, NAT Gateway usage, and Internet egress can be significantly reduced with VPC endpoints and architecture adjustments.",
            "resource": "aws-prod:DataTransfer",
            "estimated_savings": 1800,
            "priority": "high",
            "confidence_score": 0.80,
            "rationale": "Data Transfer costs often appear invisible until the bill arrives. VPC endpoints eliminate NAT Gateway charges for AWS service traffic. Co-locating compute and data in the same AZ removes inter-AZ charges entirely.",
            "effort_level": "medium",
            "action_steps": [
                "Run AWS Cost Explorer filtered by 'Data Transfer' service to identify top egress sources.",
                "Create VPC endpoints for S3, DynamoDB, and other frequently accessed AWS services.",
                "Move compute workloads to the same AZ as their primary data store to eliminate inter-AZ fees.",
                "Enable CloudFront for public-facing assets to reduce direct S3/EC2 egress.",
                "Review NAT Gateway logs — replace with VPC endpoints where possible.",
            ],
        },
        {
            "category": "ri_timing",
            "title": "Optimise Reserved Instance purchase timing and sizing",
            "description": "45% of your compute is already covered by commitments, leaving a 30% coverage gap to the recommended 75% target. Purchasing $3,840/month in additional 1-year Savings Plan commitments now — while spend is stable and trending up — would save $17,472/year.",
            "resource": "aws-prod:EC2/Commitments",
            "estimated_savings": 4320,
            "priority": "high",
            "confidence_score": 0.88,
            "rationale": "Spend has been stable (CV < 10%) for 3 consecutive months and is trending +4.2%. This is the optimal window to lock in 1-year commitments. Waiting increases risk of on-demand cost escalation. A Compute Savings Plan provides the same discount with cross-service flexibility.",
            "effort_level": "low",
            "action_steps": [
                "Open AWS Cost Explorer → Savings Plans → Purchase Recommendations.",
                "Select 'Compute Savings Plan', 1-year, no-upfront for maximum flexibility.",
                "Start with 60% of the recommended commitment to validate savings before full rollout.",
                "Review utilisation weekly for the first month to confirm steady-state baseline.",
                "Increase commitment in 10% increments each month until 75% coverage is reached.",
            ],
        },
        {
            "category": "tagging",
            "title": "Enforce resource tagging to unlock attribution and eliminate waste",
            "description": "An estimated 28% of your cloud spend is untagged, making it impossible to attribute costs to teams, projects, or environments. Untagged resources are also 3x more likely to be orphaned waste.",
            "resource": "aws-shared:Tagging",
            "estimated_savings": 2600,
            "priority": "high",
            "confidence_score": 0.78,
            "rationale": "Without tags, cost attribution is guesswork. Teams overprovision because they can't see their spend. Tagging enforcement combined with showback reports drives a natural 10-15% reduction in usage as teams become accountable.",
            "effort_level": "low",
            "action_steps": [
                "Define a mandatory tag policy: Environment, Team, CostCenter, Project, Owner.",
                "Use AWS Config rules or tag policies to flag non-compliant resources.",
                "Block resource creation without required tags via SCP (Service Control Policy).",
                "Run weekly untagged resource reports and assign cleanup ownership per team.",
                "Implement showback dashboards so each team can see their attributed spend.",
            ],
        },
    ]
    for item in recommendations:
        save_recommendation(
            username=username,
            category=item["category"],
            title=item["title"],
            description=item["description"],
            source="optimization_insights",
            resource=item["resource"],
            estimated_savings=item["estimated_savings"],
            priority=item["priority"],
            confidence_score=item["confidence_score"],
            rationale=item["rationale"],
            effort_level=item["effort_level"],
            action_steps=item["action_steps"],
        )


def render_optimization_insights_page():
    if not st.session_state.get("authenticated"):
        st.warning("Please login from the main page")
        st.stop()

    username = st.session_state.get("username", "guest")
    role = st.session_state.get("role", "user")
    st.title("Optimization Insights")
    st.write("Review cost-saving opportunities and manage them as workflow items.")

    # Commitment Utilization Dashboard
    st.subheader("Commitment Utilization Status")
    col1, col2, col3, col4 = st.columns(4)
    
    # Mock data (in production, this would come from AWS Cost Explorer API)
    monthly_commitment = 8500  # RI/Savings Plans monthly cost
    on_demand_equivalent = 5950  # Current usage in on-demand terms
    utilization_rate = round((on_demand_equivalent / monthly_commitment) * 100, 1)
    excess_monthly = monthly_commitment - on_demand_equivalent
    
    col1.metric("RI/Savings Plans Cost", f"${monthly_commitment:,.0f}/mo")
    col2.metric("Utilization Rate", f"{utilization_rate}%", delta="-15%" if utilization_rate < 70 else "+5%")
    col3.metric("Excess Capacity", f"${excess_monthly:,.0f}/mo", delta_color="inverse")
    col4.metric("Annual Waste", f"${excess_monthly * 12:,.0f}", delta_color="inverse")
    
    if utilization_rate < 70:
        st.warning(f"⚠️ Commitment utilization is low ({utilization_rate}%). Review existing reservations and consider consolidation.")

    opportunities = pd.DataFrame(
        {
            "Resource": ["EC2 Instances", "Spot Instances", "Savings Plans/RI", "RI Purchase Timing", "Scheduled EC2", "Network/Egress", "RDS Instances", "Tagging/Attribution", "EBS Volumes", "S3 Storage"],
            "Est. Savings/Year ($)": [4200, 6800, 3400, 4320, 2800, 1800, 2100, 2600, 800, 1200],
            "Priority": ["High", "High", "High", "High", "High", "High", "High", "High", "Medium", "Medium"],
            "Effort": ["Medium", "High", "Low", "Low", "Medium", "Medium", "Medium", "Low", "Low", "Low"],
        }
    )
    st.subheader("Top Optimization Opportunities")
    st.dataframe(opportunities, width="stretch", hide_index=True)

    # RI Purchase Timing
    st.subheader("Reserved Instance & Savings Plans Purchase Timing")

    # Mock 12-month cost history (in production, from AWS Cost Explorer monthly totals)
    monthly_cost_history = [48200, 49100, 50300, 51000, 50800, 52100, 51900, 53200, 52800, 54100, 53600, 53661]
    on_demand_monthly = 53661.0
    existing_ri_coverage = 0.45

    ri_analysis = recommend_ri_purchase_timing(monthly_cost_history, on_demand_monthly, existing_ri_coverage)

    ri_col1, ri_col2, ri_col3, ri_col4 = st.columns(4)
    signal = ri_analysis.get("timing_signal", "N/A")
    signal_color = {"BUY NOW": "🟢", "PARTIAL BUY": "🟡", "WAIT": "🟠", "HOLD": "🔴"}.get(signal, "⚪")
    ri_col1.metric("Timing Signal", f"{signal_color} {signal}")
    ri_col2.metric("Current RI Coverage", f"{ri_analysis['existing_ri_coverage_pct']}%", delta=f"-{ri_analysis['coverage_gap_pct']}% to target", delta_color="inverse")
    ri_col3.metric("Uncovered Spend", f"${ri_analysis['uncovered_monthly_spend']:,.0f}/mo")
    ri_col4.metric("Spend Trend (3M)", f"{'+' if ri_analysis['trend_pct'] >= 0 else ''}{ri_analysis['trend_pct']}%", delta_color="normal" if ri_analysis['trend_pct'] >= 0 else "inverse")

    st.info(f"**Timing Analysis:** {ri_analysis['timing_reason']}")

    with st.expander("Purchase Option Comparison"):
        options_data = pd.DataFrame([
            {
                "Commitment Type": opt["type"],
                "Monthly Commitment ($)": f"${opt['commitment_monthly']:,.0f}",
                "Monthly Savings ($)": f"${opt['monthly_savings']:,.0f}",
                "Annual Savings ($)": f"${opt['annual_savings']:,.0f}",
                "Risk": opt["risk"].title(),
                "Note": opt.get("note", "—"),
            }
            for opt in ri_analysis["purchase_options"]
        ])
        st.dataframe(options_data, width="stretch", hide_index=True)

        best = ri_analysis["best_option"]
        st.success(
            f"**Recommended:** {best['type']} — "
            f"saves **${best['monthly_savings']:,.0f}/month** (${best['annual_savings']:,.0f}/year). "
            f"No upfront payment; cancel anytime after 1 year."
        )

    with st.expander("Coverage Gap Analysis & Sizing Guide"):
        st.markdown(f"""
**Current state**
| Metric | Value |
|---|---|
| Average monthly spend (12M) | ${ri_analysis['avg_monthly_cost']:,.0f} |
| 3-month rolling average | ${ri_analysis['recent_3m_avg']:,.0f} |
| Spend volatility (CV) | {ri_analysis['spend_volatility_cv']}% |
| Existing commitment coverage | {ri_analysis['existing_ri_coverage_pct']}% |
| Industry target coverage | 75% |
| Coverage gap | {ri_analysis['coverage_gap_pct']}% |

**Sizing strategy**
1. **Identify steady-state baseline**: Use the lowest monthly spend in the last 6 months as your safe commitment floor.
2. **Cover 60% first**: Purchase Savings Plans for 60% of baseline — review utilisation after 30 days.
3. **Grow in 10% steps**: Increase monthly until you reach 70–75% coverage.
4. **Never commit variable peaks**: Keep bursty or seasonal workloads on Spot or on-demand.
5. **Prefer Compute Savings Plans**: They apply across EC2 instance families, Fargate, and Lambda — far more flexible than EC2 Instance Savings Plans or specific RIs.
        """)

    # Network / Data Transfer Analysis
    st.subheader("Network & Data Transfer Cost Analysis")
    net_col1, net_col2, net_col3, net_col4 = st.columns(4)

    # Mock data (in production sourced from AWS Cost Explorer Data Transfer breakdown)
    total_data_transfer_cost = 1730.46
    nat_gateway_cost = 680.00
    cross_region_cost = 540.00
    internet_egress_cost = 510.46

    net_col1.metric("Total Data Transfer", f"${total_data_transfer_cost:,.0f}/mo")
    net_col2.metric("NAT Gateway", f"${nat_gateway_cost:,.0f}/mo", help="High NAT costs suggest VPC endpoints can reduce this")
    net_col3.metric("Cross-Region", f"${cross_region_cost:,.0f}/mo", help="Co-locating data and compute eliminates this")
    net_col4.metric("Internet Egress", f"${internet_egress_cost:,.0f}/mo", help="CloudFront can reduce direct egress charges")

    nat_savings_potential = nat_gateway_cost * 0.70
    cross_region_savings = cross_region_cost * 0.60
    egress_savings = internet_egress_cost * 0.40
    total_network_savings = nat_savings_potential + cross_region_savings + egress_savings

    if total_data_transfer_cost > 500:
        st.warning(
            f"📡 Data transfer costs are significant (${total_data_transfer_cost:,.0f}/mo). "
            f"Estimated savings potential: **${total_network_savings:,.0f}/mo** through VPC endpoints, AZ co-location, and CloudFront."
        )

    with st.expander("Network Optimization Breakdown"):
        network_breakdown = pd.DataFrame({
            "Cost Type": ["NAT Gateway traffic", "Cross-region data transfer", "Internet egress (S3/EC2)", "Inter-AZ traffic"],
            "Monthly Cost ($)": [nat_gateway_cost, cross_region_cost, internet_egress_cost, round(total_data_transfer_cost - nat_gateway_cost - cross_region_cost - internet_egress_cost, 2)],
            "Recommended Action": [
                "Create VPC Interface Endpoints for S3, DynamoDB, SSM",
                "Consolidate workloads to single region where possible",
                "Route via CloudFront; cache static assets at edge",
                "Move compute to same AZ as primary data store",
            ],
            "Est. Reduction": ["~70%", "~60%", "~40%", "~80%"],
        })
        st.dataframe(network_breakdown, width="stretch", hide_index=True)
        st.info("ℹ️ VPC endpoint creation is free; you pay only for data processed through them, which is typically 40-70% cheaper than NAT Gateway rates.")

    # Tagging ROI Analysis
    st.subheader("Tagging Coverage & Attribution ROI")
    tag_col1, tag_col2, tag_col3, tag_col4 = st.columns(4)

    # Mock data (in production, derived from AWS Resource Groups Tagging API)
    total_monthly_spend = 53660.90
    untagged_spend = total_monthly_spend * 0.28       # 28% untagged
    partially_tagged_spend = total_monthly_spend * 0.22  # 22% partially tagged
    fully_tagged_spend = total_monthly_spend - untagged_spend - partially_tagged_spend
    tagging_coverage_pct = round((fully_tagged_spend / total_monthly_spend) * 100, 1)

    tag_col1.metric("Tagging Coverage", f"{tagging_coverage_pct}%", delta="-28% gap", delta_color="inverse")
    tag_col2.metric("Unattributed Spend", f"${untagged_spend:,.0f}/mo", help="Spend with no tags — cannot be assigned to team or project")
    tag_col3.metric("Partially Tagged", f"${partially_tagged_spend:,.0f}/mo", help="Has some tags but missing required fields (e.g. CostCenter, Environment)")
    tag_col4.metric("Attribution Savings*", f"${untagged_spend * 0.12:,.0f}/mo", help="*Teams with cost visibility reduce spend 10–15% on average")

    if tagging_coverage_pct < 80:
        st.warning(
            f"🏷️ Only {tagging_coverage_pct}% of spend is fully tagged. "
            f"**${untagged_spend:,.0f}/month** cannot be attributed to any team or project — "
            "making it impossible to hold anyone accountable or detect orphaned resources."
        )

    with st.expander("Tagging Gap Breakdown by Service"):
        tagging_detail = pd.DataFrame({
            "Service": ["EC2", "RDS", "Lambda", "EBS", "S3", "ELB", "CloudWatch"],
            "Monthly Spend ($)": [10510, 5107, 2100, 1800, 2053, 980, 640],
            "Tagged (%)": [72, 85, 45, 30, 60, 20, 10],
            "Missing Tags": ["CostCenter, Owner", "Environment", "Team, CostCenter, Owner", "Owner, Project", "CostCenter", "All required tags", "All required tags"],
            "Risk": ["Medium", "Low", "High", "High", "Medium", "Critical", "Critical"],
        })
        st.dataframe(tagging_detail, width="stretch", hide_index=True)

    with st.expander("Recommended Tag Policy"):
        st.markdown("""
**Mandatory tags (block resource creation without these):**
| Tag Key | Example Values | Purpose |
|---|---|---|
| `Environment` | prod, staging, dev, test | Isolate cost by lifecycle |
| `Team` | platform, data-eng, finops | Attribute to engineering team |
| `CostCenter` | CC-1042, CC-2091 | Finance chargeback |
| `Project` | payments-v2, migration-q1 | Per-project reporting |
| `Owner` | user@company.com | Accountability and escalation |

**Enforcement options:**
- **AWS Config**: Alert on non-compliant resources (reactive)
- **SCP (Service Control Policy)**: Block creation without required tags (proactive)
- **AWS Tag Editor**: Bulk-apply missing tags across accounts
        """)

    # Cost Anomaly Detection Dashboard
    st.subheader("Cost Anomaly Detection & Alerts")
    anom_col1, anom_col2, anom_col3 = st.columns(3)
    
    # Mock anomaly data (in production, from AWS Cost Anomaly Detector API)
    baseline_daily = 215.50
    recent_daily = 258.75
    spike_percent = ((recent_daily - baseline_daily) / baseline_daily * 100)
    
    anom_col1.metric("Baseline Daily Avg", f"${baseline_daily:,.2f}")
    anom_col2.metric("Recent 7-Day Avg", f"${recent_daily:,.2f}", delta=f"+{spike_percent:.1f}%")
    anom_col3.metric("Spike Detection", "⚠️ Alert" if spike_percent > 15 else "✓ Normal")
    
    if spike_percent > 15:
        st.warning(f"📊 Cost spike detected! Recent spending is {spike_percent:.1f}% above baseline. Review service-level costs below:")
        
        # Service-level spike detection
        service_spikes = pd.DataFrame({
            "Service": ["EC2", "RDS", "Lambda", "S3"],
            "This Month ($)": [3840, 1250, 580, 420],
            "Last Month Avg ($)": [3200, 1100, 650, 400],
            "Change (%)": ["+20%", "+13.6%", "-10.8%", "+5%"],
        })
        st.dataframe(service_spikes, width="stretch", hide_index=True)
    
    # Budget configuration
    monthly_budget = 12000
    current_spend = 8950
    budget_percent = (current_spend / monthly_budget) * 100
    
    with st.expander("Budget Threshold Configuration"):
        st.markdown(f"**Monthly Budget**: ${monthly_budget:,.0f}")
        st.markdown(f"**Current Spend**: ${current_spend:,.0f} ({budget_percent:.1f}%)")
        st.progress(budget_percent / 100, text=f"{budget_percent:.1f}% used")
        st.info("✓ Budget alerts configured at 70% ($8,400), 85% ($10,200), and 100% ($12,000)")

    if st.button("Save Monitoring Recommendations to Workflow", width="stretch"):
        _seed_optimization_recommendations(username)
        show_toast(*TOAST_OPT_WORKFLOW_SAVED)
        st.rerun()

    workflow_items = list_recommendations(username=username, source="optimization_insights", limit=20)
    if role not in {"admin", "premium"}:
        workflow_items = [item for item in workflow_items if can_manage_recommendation(item, username, action="view")]
    if not workflow_items:
        clicked = render_empty_state(
            icon="💡",
            title="No optimization workflow items yet",
            message="Save the current opportunities above to create trackable workflow items with owners, due dates, and savings tracking.",
            cta_label="Save Opportunities to Workflow",
            cta_key="empty_save_opt_workflow",
        )
        if clicked:
            _seed_optimization_recommendations(username)
            show_toast(*TOAST_OPT_WORKFLOW_SAVED)
            st.rerun()
        return

    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("Open", sum(1 for item in workflow_items if item.get("status") in {"new", "accepted"}))
    summary_col2.metric("Completed", sum(1 for item in workflow_items if item.get("status") == "completed"))
    summary_col3.metric(
        "Potential Savings",
        f"${sum(float(item.get('estimated_savings') or 0) for item in workflow_items):,.0f}",
    )

    for item in workflow_items:
        with st.container(border=True):
            can_edit_details = can_manage_recommendation(item, username, action="details")
            can_accept = can_manage_recommendation(item, username, action="accept")
            header_col, status_col = st.columns([3, 1])
            header_col.markdown(f"**{item['title']}**")
            header_col.caption(item.get("description") or "")
            status_col.metric("Status", item.get("status", "new").title())

            meta_col1, meta_col2, meta_col3 = st.columns(3)
            owner_value = meta_col1.text_input(
                "Owner",
                value=item.get("owner") or "",
                key=f"opt_owner_{item['id']}",
                disabled=role not in {"admin", "premium"},
            )
            priority_options = ["high", "medium", "low"]
            current_priority = str(item.get("priority") or "medium").lower()
            priority_value = meta_col2.selectbox(
                "Priority",
                priority_options,
                index=priority_options.index(current_priority) if current_priority in priority_options else 1,
                key=f"opt_priority_{item['id']}",
            )
            due_date_value = meta_col3.date_input(
                "Due date",
                value=pd.to_datetime(item.get("due_date")).date() if item.get("due_date") else date.today(),
                key=f"opt_due_{item['id']}",
                disabled=not can_edit_details,
            )

            action_col1, action_col2, action_col3, action_col4 = st.columns(4)
            if action_col1.button("Save Details", key=f"opt_save_{item['id']}", width="stretch", disabled=not can_edit_details):
                updated = update_recommendation_details(
                    recommendation_id=item["id"],
                    username=username,
                    owner=owner_value or None,
                    priority=priority_value,
                    due_date=due_date_value.isoformat() if due_date_value else None,
                    notes="Updated from optimization insights",
                )
                if updated:
                    show_toast(*TOAST_OPT_DETAILS_SAVED)
                    st.rerun()
                st.error("You do not have permission to update this recommendation.")
            if action_col2.button("Accept", key=f"opt_accept_{item['id']}", width="stretch", disabled=not can_accept):
                updated = update_recommendation_status(
                    item["id"],
                    "accepted",
                    username=username,
                    owner=username if role not in {"admin", "premium"} else None,
                    notes="Accepted from optimization insights",
                )
                if updated:
                    show_toast(*TOAST_OPT_ACCEPTED)
                    st.rerun()
                st.error("You do not have permission to accept this recommendation.")
            if action_col3.button("Complete", key=f"opt_complete_{item['id']}", width="stretch", disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "completed", username=username, notes="Completed from optimization insights")
                if updated:
                    show_toast(*TOAST_OPT_COMPLETED)
                    st.rerun()
                st.error("You do not have permission to complete this recommendation.")
            if action_col4.button("Snooze", key=f"opt_snooze_{item['id']}", width="stretch", disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "snoozed", username=username, notes="Snoozed from optimization insights")
                if updated:
                    show_toast(*TOAST_OPT_SNOOZED)
                    st.rerun()
                st.error("You do not have permission to snooze this recommendation.")

    # What-If Scenario Calculator
    st.divider()
    st.subheader("💡 What-If Scenario Calculator")
    st.write("Model the cost impact of implementing different combinations of optimizations.")
    
    with st.expander("Configure Optimization Scenario"):
        calc_col1, calc_col2 = st.columns(2)
        
        with calc_col1:
            current_monthly = st.number_input(
                "Current Monthly Cost ($)",
                min_value=100,
                max_value=500000,
                value=18500,
                step=100,
                help="Total monthly AWS spend"
            )
        
        with calc_col2:
            st.markdown("**Select Optimizations to Apply:**")
        
        # Optimization checkboxes
        opt_rightsizing_ec2 = st.checkbox("EC2 Rightsizing (-15%)", value=True)
        opt_spot = st.checkbox("Migrate to Spot Instances (-35%)", value=False)
        opt_commitments = st.checkbox("Optimize Commitments (-18%)", value=True)
        opt_scheduling = st.checkbox("Scheduled Scaling (-15%)", value=False)
        opt_storage = st.checkbox("Storage Optimization (-8%)", value=True)
        opt_database = st.checkbox("Database Rightsizing (-12%)", value=False)
        
        # Build optimization list
        optimizations = []
        if opt_rightsizing_ec2:
            optimizations.append({"name": "EC2 Rightsizing", "savings_percent": 15})
        if opt_spot:
            optimizations.append({"name": "Spot Instances", "savings_percent": 35})
        if opt_commitments:
            optimizations.append({"name": "Commitment Optimization", "savings_percent": 18})
        if opt_scheduling:
            optimizations.append({"name": "Scheduled Scaling", "savings_percent": 15})
        if opt_storage:
            optimizations.append({"name": "Storage Optimization", "savings_percent": 8})
        if opt_database:
            optimizations.append({"name": "Database Rightsizing", "savings_percent": 12})
        
        if st.button("Calculate Scenario Impact", width="stretch"):
            from services.optimization_engine import calculate_scenario_savings
            
            results = calculate_scenario_savings(current_monthly, optimizations)
            
            if "scenario_errors" not in results:
                st.success("✓ Scenario calculated successfully!")
                
                # Summary metrics
                summary_col1, summary_col2, summary_col3 = st.columns(3)
                summary_col1.metric("Baseline Cost", f"${results['baseline_monthly']:,.0f}/mo")
                summary_col2.metric("Projected Cost", f"${results['new_monthly_cost']:,.0f}/mo")
                summary_col3.metric("Total Savings", f"${results['total_savings_monthly']:,.0f}/mo (+{results['cumulative_savings_percent']:.1f}%)")
                
                # Detailed breakdown
                st.markdown("**Savings Breakdown by Optimization:**")
                breakdown_df = pd.DataFrame([
                    {
                        "Optimization": opt["name"],
                        "Savings %": f"{opt['savings_percent']}%",
                        "Monthly Savings": f"${opt['savings_monthly']:,.0f}",
                        "Annual Savings": f"${opt['savings_annual']:,.0f}",
                    }
                    for opt in results["optimizations"]
                ])
                st.dataframe(breakdown_df, width="stretch", hide_index=True)
                
                # Annual projections
                st.markdown("**Annual Projection:**")
                annual_col1, annual_col2, annual_col3 = st.columns(3)
                annual_col1.metric("Baseline Annual", f"${results['baseline_monthly'] * 12:,.0f}/year")
                annual_col2.metric("Projected Annual", f"${results['new_monthly_cost'] * 12:,.0f}/year")
                annual_col3.metric("Total Savings", f"${results['total_savings_annual']:,.0f}/year")


