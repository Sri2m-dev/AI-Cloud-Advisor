"""ACT-013 assembled-product acceptance over the certified production services."""

from tests.universal_evidence.test_act012c_final_security import (
    test_controlled_enterprise_consolidated_scoped_ask_journey as _enterprise_journey,
)
from tests.universal_evidence.test_act012c_final_security import (
    test_synthetic_cur_consolidated_adversarial_journey_blocks_money_authority as _cur_journey,
)
from tests.universal_evidence.test_pue_integrated_restart import (
    test_activation_kill_switch_and_scoped_purge_survive_restart as _policy_restart,
)
from tests.universal_evidence.test_pue_integrated_restart import (
    test_full_governed_stack_survives_restart as _full_restart,
)


def test_complete_production_service_journey_survives_restart(tmp_path):
    """One CI gate for CUR, enterprise context, security, lifecycle, and restart."""
    _cur_journey()
    _enterprise_journey()
    full = tmp_path / "full"
    policy = tmp_path / "policy"
    full.mkdir()
    policy.mkdir()
    _full_restart(full)
    _policy_restart(policy)
