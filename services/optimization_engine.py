# 2_Optimization.py
import streamlit as st
import pandas as pd

# Idle resource detection function
def find_idle_resources(resources):
    idle = resources[
        (resources["cpu_utilization"] < 10) &
        (resources["network"] < 5)
    ]
    return idle

# Reserved Instance / Savings Plan recommendation function
def ri_recommendation(usage_hours):
    if usage_hours > 500:
        return "Recommended: Purchase Reserved Instance"
    elif usage_hours > 300:
        return "Consider Savings Plan"
    else:
        return "On-demand is optimal"

# Spot Instances optimization
def calculate_spot_savings(ec2_monthly_cost, utilization_avg=0.6):
    """
    Calculate potential savings from switching to Spot Instances.
    Spot instances offer up to 90% discount vs on-demand.
    Suitable for fault-tolerant, stateless workloads.
    
    Args:
        ec2_monthly_cost: Current monthly EC2 on-demand cost
        utilization_avg: Average utilization rate (0.0-1.0)
    
    Returns:
        dict with spot savings details
    """
    # Conservative estimate: 70% discount (realistic range 50-90%)
    spot_discount = 0.70
    
    # Not all workloads are suitable for Spot (assume 60% can be converted)
    suitable_workload_ratio = 0.60
    
    eligible_cost = ec2_monthly_cost * suitable_workload_ratio
    spot_savings_monthly = eligible_cost * spot_discount
    spot_savings_annual = spot_savings_monthly * 12
    
    return {
        "eligible_cost": eligible_cost,
        "monthly_savings": spot_savings_monthly,
        "annual_savings": spot_savings_annual,
        "discount_percent": int(spot_discount * 100),
        "eligible_workload_ratio": int(suitable_workload_ratio * 100),
    }

# RI and Savings Plans Utilization Tracking
def calculate_commitment_utilization(monthly_commitment_cost, on_demand_usage_cost):
    """
    Calculate RI/Savings Plans utilization rate and coverage ratio.
    
    Args:
        monthly_commitment_cost: Monthly cost of RI/Savings Plans commitment
        on_demand_usage_cost: Current on-demand equivalent usage cost
    
    Returns:
        dict with utilization metrics and insights
    """
    if monthly_commitment_cost <= 0:
        return {
            "utilization_rate": 0,
            "coverage_ratio": 0,
            "status": "no_commitments",
            "opportunity": None,
        }
    
    # Utilization rate: what percentage of commitment is being used
    utilization_rate = min((on_demand_usage_cost / monthly_commitment_cost) * 100, 100)
    
    # Coverage ratio: what percentage of on-demand usage is covered by commitment
    if on_demand_usage_cost > 0:
        coverage_ratio = (monthly_commitment_cost / on_demand_usage_cost) * 100
    else:
        coverage_ratio = 0
    
    # Classify utilization health
    if utilization_rate >= 85:
        status = "healthy"
        opportunity = None
    elif utilization_rate >= 70:
        status = "good"
        opportunity = "Consider increasing commitment to improve coverage"
    else:
        status = "underutilized"
        # Calculate break-even: excess commitment wasted
        excess_monthly = monthly_commitment_cost - on_demand_usage_cost
        opportunity = f"Commitment underutilized; ${excess_monthly:.0f}/month excess. Consider downsizing."
    
    return {
        "utilization_rate": round(utilization_rate, 1),
        "coverage_ratio": round(coverage_ratio, 1),
        "status": status,
        "opportunity": opportunity,
        "on_demand_equivalent": on_demand_usage_cost,
        "current_commitment": monthly_commitment_cost,
    }

def identify_underutilized_commitments(monthly_commitment_cost, on_demand_usage_cost, savings_threshold=500):
    """
    Identify if commitments are significantly underutilized and calculate recovery potential.
    
    Args:
        monthly_commitment_cost: Monthly RI/Savings Plans cost
        on_demand_usage_cost: Current on-demand equivalent usage
        savings_threshold: Minimum monthly savings to flag as opportunity ($)
    
    Returns:
        dict with recovery opportunity details
    """
    utilization = calculate_commitment_utilization(monthly_commitment_cost, on_demand_usage_cost)
    
    if utilization["status"] == "no_commitments":
        return None
    
    # Calculate excess commitment
    excess_monthly = max(monthly_commitment_cost - on_demand_usage_cost, 0)
    excess_annual = excess_monthly * 12
    
    if excess_annual < savings_threshold:
        return None
    
    # Confidence based on utilization consistency
    confidence = 0.95 if utilization["utilization_rate"] < 50 else 0.80
    
    return {
        "type": "commitment_optimization",
        "excess_monthly": excess_monthly,
        "excess_annual": excess_annual,
        "current_utilization": utilization["utilization_rate"],
        "confidence_score": confidence,
        "recovery_opportunity": f"Rightsize or consolidate underutilized commitments to recover ${excess_annual:.0f}/year",
    }

# Auto-Scaling and Scheduled Scaling Recommendations
def analyze_scheduling_opportunity(workload_type, peak_hours_daily, off_peak_multiplier=0.3):
    """
    Analyze if a workload is suitable for scheduled stop/start or auto-scaling optimization.
    
    Args:
        workload_type: Type of workload ('batch', 'dev', 'periodic', 'predictable')
        peak_hours_daily: Hours per day when workload is active (e.g., 8 for business hours)
        off_peak_multiplier: Resource utilization during off-peak (0.0-1.0)
    
    Returns:
        dict with scheduling opportunity details
    """
    total_hours = 24
    off_peak_hours = total_hours - peak_hours_daily
    
    # Calculate potential cost reduction from scheduling
    # Assumption: running at off_peak_multiplier resources during off-peak
    resource_savings_ratio = (off_peak_hours * (1 - off_peak_multiplier)) / total_hours
    
    # Workload suitability scoring
    suitability_score = {
        'batch': 0.95,      # Batch jobs highly suitable
        'dev': 0.85,        # Dev environments good fit
        'periodic': 0.90,   # Periodic tasks (backups, reports)
        'predictable': 0.75, # Predictable but some complexity
    }.get(workload_type, 0.60)
    
    # Minimum savings threshold
    monthly_savings_estimate = resource_savings_ratio * 100 * 30  # $100/month baseline
    annual_savings = monthly_savings_estimate * 12
    
    return {
        "workload_type": workload_type,
        "peak_hours_daily": peak_hours_daily,
        "resource_savings_ratio": round(resource_savings_ratio * 100, 1),
        "annual_savings_estimate": annual_savings,
        "suitability_score": suitability_score,
        "suitable": suitability_score >= 0.75 and annual_savings >= 600,
    }

def identify_scheduling_candidates(ec2_monthly_cost, dev_env_ratio=0.25):
    """
    Identify EC2 resources that could benefit from scheduled scaling.
    
    Args:
        ec2_monthly_cost: Total EC2 monthly cost
        dev_env_ratio: Estimated ratio of dev/test environments (0.0-1.0)
    
    Returns:
        dict with scheduling opportunity summary
    """
    dev_env_cost = ec2_monthly_cost * dev_env_ratio
    
    # Dev/test environments typically unused 16 hours/day (only business hours usage)
    business_hours = 8
    unused_hours_ratio = (24 - business_hours) / 24
    
    monthly_savings = dev_env_cost * unused_hours_ratio * 0.80  # 80% of unused can be stopped
    annual_savings = monthly_savings * 12
    
    # Workload candidates
    candidates = [
        {
            "workload": "Development/Test EC2 instances",
            "suitability": "High",
            "potential_savings_annual": annual_savings * 0.6,
            "risk": "Low",
        },
        {
            "workload": "Batch processing jobs (non-production)",
            "suitability": "High",
            "potential_savings_annual": annual_savings * 0.3,
            "risk": "Low",
        },
        {
            "workload": "Non-critical background services",
            "suitability": "Medium",
            "potential_savings_annual": annual_savings * 0.1,
            "risk": "Medium",
        },
    ]
    
    return {
        "total_annual_savings": annual_savings,
        "estimated_candidates": len(candidates),
        "candidates": candidates,
        "implementation_notes": "Use EventBridge + Systems Manager or Lambda for automated scheduling",
    }

# Cost Anomaly Detection and Alerting
def detect_cost_anomaly(daily_costs, threshold_percent=20):
    """
    Detect unusual spending patterns using statistical analysis.
    
    Args:
        daily_costs: List of daily costs (most recent 30 days)
        threshold_percent: Alert if variance exceeds this % (default 20%)
    
    Returns:
        dict with anomaly detection results
    """
    import statistics
    
    if not daily_costs or len(daily_costs) < 7:
        return {"anomaly_detected": False, "reason": "Insufficient data"}
    
    # Calculate baseline (first 21 days) vs recent (last 7 days)
    baseline_window = daily_costs[:21] if len(daily_costs) > 21 else daily_costs[:7]
    recent_window = daily_costs[-7:]
    
    baseline_avg = statistics.mean(baseline_window)
    baseline_std = statistics.stdev(baseline_window) if len(baseline_window) > 1 else 0
    recent_avg = statistics.mean(recent_window)
    
    # Detect spike
    spike_percent = ((recent_avg - baseline_avg) / baseline_avg * 100) if baseline_avg > 0 else 0
    
    # Statistical detection: > 2 std devs or > threshold_percent increase
    threshold_exceeded = spike_percent > threshold_percent
    statistical_anomaly = recent_avg > (baseline_avg + 2 * baseline_std) if baseline_std > 0 else False
    
    anomaly_detected = threshold_exceeded or statistical_anomaly
    
    return {
        "anomaly_detected": anomaly_detected,
        "baseline_daily_avg": round(baseline_avg, 2),
        "recent_daily_avg": round(recent_avg, 2),
        "spike_percent": round(spike_percent, 1),
        "threshold_percent": threshold_percent,
        "recent_trend": "increasing" if spike_percent > 0 else "decreasing",
    }

def set_cost_threshold_alert(monthly_budget, alert_percentage=85):
    """
    Create a cost threshold alert based on monthly budget.
    
    Args:
        monthly_budget: Target monthly budget
        alert_percentage: Alert when spending reaches this % of budget (default 85%)
    
    Returns:
        dict with alert configuration
    """
    alert_threshold = (monthly_budget * alert_percentage) / 100
    warning_threshold = (monthly_budget * 70) / 100
    
    return {
        "monthly_budget": monthly_budget,
        "alert_threshold": round(alert_threshold, 2),
        "warning_threshold": round(warning_threshold, 2),
        "alert_level_percent": alert_percentage,
        "alert_type": "budget_tracking",
        "recommendation": f"Configure AWS Budgets to send notifications when spending reaches ${alert_threshold:,.0f} ({alert_percentage}% of budget)",
        "cloudwatch_integration": True,
    }

def identify_service_cost_spikes(service_costs, services_to_monitor=None):
    """
    Identify which services are spiking in cost.
    
    Args:
        service_costs: Dict of service names to costs {service: cost}
        services_to_monitor: List of services to focus on (default: top 5)
    
    Returns:
        dict with service-level spike analysis
    """
    if not service_costs:
        return {"spikes_detected": [], "summary": "No service cost data available"}
    
    sorted_services = sorted(service_costs.items(), key=lambda x: x[1], reverse=True)
    
    if not services_to_monitor:
        services_to_monitor = [s[0] for s in sorted_services[:5]]
    
    spikes = []
    total_tracked_cost = sum(cost for service, cost in sorted_services if service in services_to_monitor)
    
    for service, cost in sorted_services:
        if service in services_to_monitor:
            percent_of_total = (cost / total_tracked_cost * 100) if total_tracked_cost > 0 else 0
            
            # Flag if > 20% of tracked services or > $1000/month
            if percent_of_total > 20 or cost > 1000:
                spikes.append({
                    "service": service,
                    "monthly_cost": round(cost, 2),
                    "percent_of_tracked": round(percent_of_total, 1),
                    "alert_level": "critical" if cost > 3000 else "warning",
                })
    
    return {
        "spikes_detected": spikes,
        "spike_count": len(spikes),
        "total_spiking_cost": sum(s["monthly_cost"] for s in spikes),
        "recommendation": "Review spike sources using AWS Cost Explorer or Trusted Advisor",
    }

# What-If Cost Scenario Modeling
def calculate_scenario_savings(current_monthly_cost, optimizations_to_apply):
    """
    Model the cost impact of applying multiple optimizations.
    
    Args:
        current_monthly_cost: Current total monthly spend
        optimizations_to_apply: List of optimization dicts with 'name' and 'savings_percent'
    
    Returns:
        dict with scenario analysis
    """
    if not optimizations_to_apply:
        return {"scenario_errors": ["No optimizations provided"]}
    
    scenario_results = {
        "baseline_monthly": current_monthly_cost,
        "optimizations": [],
        "total_savings_monthly": 0,
        "total_savings_annual": 0,
    }
    
    remaining_cost = current_monthly_cost
    
    for optimization in optimizations_to_apply:
        name = optimization.get("name", "Unknown")
        savings_percent = optimization.get("savings_percent", 0)
        
        # Calculate savings from this specific optimization
        optimization_savings = remaining_cost * (savings_percent / 100)
        
        scenario_results["optimizations"].append({
            "name": name,
            "savings_percent": savings_percent,
            "savings_monthly": round(optimization_savings, 2),
            "savings_annual": round(optimization_savings * 12, 2),
        })
        
        scenario_results["total_savings_monthly"] += optimization_savings
        remaining_cost -= optimization_savings
    
    scenario_results["total_savings_annual"] = scenario_results["total_savings_monthly"] * 12
    scenario_results["new_monthly_cost"] = round(remaining_cost, 2)
    scenario_results["cumulative_savings_percent"] = round(
        (scenario_results["total_savings_monthly"] / current_monthly_cost * 100), 1
    )
    
    return scenario_results

def compare_commitment_scenarios(current_ec2_cost, existing_ri_monthly, scenario_option="increase"):
    """
    Model cost impact of changing RI/Savings Plans commitment.
    
    Args:
        current_ec2_cost: Current on-demand equivalent EC2 cost
        existing_ri_monthly: Current RI/Savings Plans monthly cost
        scenario_option: 'increase', 'decrease', or 'consolidate'
    
    Returns:
        dict with commitment scenario comparison
    """
    scenarios = {
        "increase": {
            "description": "Increase commitment by 25% (better coverage)",
            "new_commitment": existing_ri_monthly * 1.25,
            "coverage_increase": 0.25,
            "discount_rate": 0.50,  # Avg 50% discount
        },
        "decrease": {
            "description": "Reduce commitment by 20% (lower waste)",
            "new_commitment": existing_ri_monthly * 0.80,
            "coverage_reduction": 0.20,
            "discount_rate": 0.45,
        },
        "consolidate": {
            "description": "Consolidate to optimal commitment",
            "new_commitment": current_ec2_cost * 0.55,  # 55% of on-demand
            "adjustment": "optimized",
            "discount_rate": 0.45,
        },
    }
    
    scenario = scenarios.get(scenario_option, scenarios["consolidate"])
    new_commitment = scenario["new_commitment"]
    
    # Calculate monthly and annual differences
    commitment_change = new_commitment - existing_ri_monthly
    commitment_change_annual = commitment_change * 12
    
    # On-demand costs covered by commitment
    on_demand_covered = min(current_ec2_cost, new_commitment)
    on_demand_unplanned = max(0, current_ec2_cost - new_commitment)
    
    total_monthly_cost = on_demand_covered + (on_demand_unplanned * 0.10)  # 10% markup for on-demand overflow
    on_demand_only_cost = current_ec2_cost
    
    monthly_savings = on_demand_only_cost - total_monthly_cost
    annual_savings = monthly_savings * 12
    
    return {
        "scenario_name": scenario_option,
        "scenario_description": scenario.get("description"),
        "current_commitment": round(existing_ri_monthly, 2),
        "new_commitment": round(new_commitment, 2),
        "commitment_change": round(commitment_change, 2),
        "current_monthly_cost": round(on_demand_only_cost, 2),
        "new_monthly_cost": round(total_monthly_cost, 2),
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings": round(annual_savings, 2),
        "payback_period_months": round(abs(commitment_change) / monthly_savings, 1) if monthly_savings > 0 else 0,
    }

def model_rightsizing_impact(resources_data, rightsizing_ratio=0.15):
    """
    Model cost impact of rightsizing resources.
    
    Args:
        resources_data: List of resources with costs
        rightsizing_ratio: Estimated cost savings % from rightsizing (default 15%)
    
    Returns:
        dict with rightsizing impact
    """
    total_current = sum(r.get("cost", 0) for r in resources_data) if resources_data else 0
    
    if total_current <= 0:
        return {"error": "No resource cost data provided"}
    
    rightsizing_savings = total_current * (rightsizing_ratio / 100)
    
    return {
        "current_monthly_cost": round(total_current, 2),
        "rightsizing_savings_percent": rightsizing_ratio,
        "rightsizing_savings_monthly": round(rightsizing_savings, 2),
        "rightsizing_savings_annual": round(rightsizing_savings * 12, 2),
        "projected_cost_after": round(total_current - rightsizing_savings, 2),
        "resource_count": len(resources_data),
    }

st.info("Recommendation: Remove unattached EBS volumes")