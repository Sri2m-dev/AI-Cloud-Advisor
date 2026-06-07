from typing import Dict, Any, List

class RuleEngine:
    @staticmethod
    def evaluate(approval: Dict[str, Any]) -> List[str]:
        actions = []
        if approval.get('spend_risk', 0) > 10000:
            actions.append('require_finance_approval')
        if str(approval.get('security_risk', '')).upper() == 'HIGH':
            actions.append('require_security_team')
        if approval.get('idle_days', 0) > 30:
            actions.append('auto_generate_recommendation')
        return actions

