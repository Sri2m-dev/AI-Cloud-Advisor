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
            "Resource": ["EC2 Instances", "Spot Instances", "Savings Plans/RI", "Scheduled EC2", "RDS Instances", "EBS Volumes", "S3 Storage"],
            "Potential Savings ($)": [4200, 6800, 3400, 2800, 2100, 800, 1200],
            "Priority": ["High", "High", "High", "High", "High", "Medium", "Medium"],
        }
    )
    st.subheader("Top Optimization Opportunities")
    st.dataframe(opportunities, width="stretch", hide_index=True)

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
        st.success("Monitoring recommendations saved to workflow.")
        st.rerun()

    workflow_items = list_recommendations(username=username, source="optimization_insights", limit=20)
    if role not in {"admin", "premium"}:
        workflow_items = [item for item in workflow_items if can_manage_recommendation(item, username, action="view")]
    if not workflow_items:
        st.info("No optimization workflow items yet. Save the current opportunities to start tracking them.")
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
                    st.rerun()
                st.error("You do not have permission to accept this recommendation.")
            if action_col3.button("Complete", key=f"opt_complete_{item['id']}", width="stretch", disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "completed", username=username, notes="Completed from optimization insights")
                if updated:
                    st.rerun()
                st.error("You do not have permission to complete this recommendation.")
            if action_col4.button("Snooze", key=f"opt_snooze_{item['id']}", width="stretch", disabled=not can_edit_details):
                updated = update_recommendation_status(item["id"], "snoozed", username=username, notes="Snoozed from optimization insights")
                if updated:
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


