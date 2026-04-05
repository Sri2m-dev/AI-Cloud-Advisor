def auto_optimize(usage_df, safe_mode=True):
    actions = []

    for _, row in usage_df.iterrows():
        utilization = row.get("utilization", 0)
        resource = row.get("resource", "unknown")

        # Rule 1: Idle → Stop
        if utilization < 20:
            action = {
                "resource": resource,
                "action": "STOP_INSTANCE",
                "reason": "Low utilization (<20%)"
            }

        # Rule 2: Overutilized → Scale
        elif utilization > 80:
            action = {
                "resource": resource,
                "action": "SCALE_UP",
                "reason": "High utilization (>80%)"
            }
        else:
            continue

        # Safe Mode Simulation
        if safe_mode:
            action["status"] = "Simulated"
        else:
            action["status"] = "Executed"

        actions.append(action)

    return actions
