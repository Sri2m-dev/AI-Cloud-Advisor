from typing import List, Dict
import numpy as np

def predict_monthly_spend(cost_history: List[float]) -> float:
    # Simple linear forecast (replace with ML model for production)
    if not cost_history:
        return 0.0
    x = np.arange(len(cost_history))
    y = np.array(cost_history)
    coeffs = np.polyfit(x, y, 1)
    next_month = coeffs[0] * (len(cost_history)) + coeffs[1]
    return float(max(next_month, 0))

def predict_burn_rate(cost_history: List[float]) -> float:
    if not cost_history:
        return 0.0
    return float(np.mean(np.diff(cost_history)))

def predict_budget_overrun(cost_history: List[float], budget: float) -> bool:
    forecast = predict_monthly_spend(cost_history)
    return forecast > budget

