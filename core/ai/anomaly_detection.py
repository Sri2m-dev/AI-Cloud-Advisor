from typing import List, Dict
import numpy as np

def detect_spend_spikes(cost_history: List[float], threshold_pct: float = 30.0) -> List[int]:
    spikes = []
    for i in range(1, len(cost_history)):
        if cost_history[i-1] == 0:
            continue
        pct_change = 100 * (cost_history[i] - cost_history[i-1]) / cost_history[i-1]
        if pct_change > threshold_pct:
            spikes.append(i)
    return spikes

def detect_abnormal_growth(resource_counts: List[int], threshold_pct: float = 30.0) -> List[int]:
    spikes = []
    for i in range(1, len(resource_counts)):
        if resource_counts[i-1] == 0:
            continue
        pct_change = 100 * (resource_counts[i] - resource_counts[i-1]) / resource_counts[i-1]
        if pct_change > threshold_pct:
            spikes.append(i)
    return spikes

def detect_unusual_saas_usage(usage_history: List[float], threshold_pct: float = 30.0) -> List[int]:
    spikes = []
    for i in range(1, len(usage_history)):
        if usage_history[i-1] == 0:
            continue
        pct_change = 100 * (usage_history[i] - usage_history[i-1]) / usage_history[i-1]
        if pct_change > threshold_pct:
            spikes.append(i)
    return spikes

