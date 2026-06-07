from typing import List, Dict

def generate_rightsizing_recommendations(resources: List[Dict]) -> List[Dict]:
    return [r for r in resources if r.get('utilization', 100) < 50]

def generate_cleanup_recommendations(resources: List[Dict]) -> List[Dict]:
    return [r for r in resources if r.get('status') == 'unused']

def generate_commitment_optimization(commitments: List[Dict]) -> List[Dict]:
    return [c for c in commitments if c.get('usage_pct', 100) < 70]

def generate_license_optimization(licenses: List[Dict]) -> List[Dict]:
    return [l for l in licenses if l.get('usage_pct', 100) < 60]

