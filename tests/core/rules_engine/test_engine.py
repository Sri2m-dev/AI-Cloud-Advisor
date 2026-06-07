from core.rules_engine.engine import RuleEngine

def test_require_finance_approval():
    approval = {'spend_risk': 15000}
    actions = RuleEngine.evaluate(approval)
    assert 'require_finance_approval' in actions

def test_require_security_team():
    approval = {'security_risk': 'HIGH'}
    actions = RuleEngine.evaluate(approval)
    assert 'require_security_team' in actions

def test_auto_generate_recommendation():
    approval = {'idle_days': 45}
    actions = RuleEngine.evaluate(approval)
    assert 'auto_generate_recommendation' in actions

def test_multiple_rules():
    approval = {'spend_risk': 20000, 'security_risk': 'HIGH', 'idle_days': 60}
    actions = RuleEngine.evaluate(approval)
    assert set(actions) == {'require_finance_approval', 'require_security_team', 'auto_generate_recommendation'}

def test_no_rules():
    approval = {'spend_risk': 100, 'security_risk': 'LOW', 'idle_days': 5}
    actions = RuleEngine.evaluate(approval)
    assert actions == []

