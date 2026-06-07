from typing import List, Dict

def governance_summary(approvals: List[Dict]) -> Dict:
    total = len(approvals)
    pending = sum(1 for a in approvals if a.get('status') == 'PENDING')
    breached = sum(1 for a in approvals if a.get('sla_status', 'ok') != 'ok')
    return {
        'total_approvals': total,
        'pending': pending,
        'sla_breached': breached
    }

def optimization_opportunities(resources: List[Dict]) -> int:
    return sum(1 for r in resources if r.get('utilization', 100) < 50 or r.get('status') == 'unused')

def risk_scoring(approvals: List[Dict]) -> float:
    if not approvals:
        return 0.0
    return sum(1 for a in approvals if a.get('risk', '').lower() == 'high') / len(approvals)

def executive_insights(approvals: List[Dict], resources: List[Dict]) -> Dict:
    return {
        'governance': governance_summary(approvals),
        'optimization': optimization_opportunities(resources),
        'risk_score': risk_scoring(approvals)
    }

