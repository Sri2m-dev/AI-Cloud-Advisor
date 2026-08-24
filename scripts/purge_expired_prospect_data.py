from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from services.prospect_data_intake_service import purge_expired  # noqa: E402


def main() -> None:
    key = os.getenv("NEXORA_PROSPECT_DATA_KEY", "").strip()
    local_key = ROOT_DIR / ".streamlit" / "prospect-data.key"
    if not key and local_key.exists():
        key = local_key.read_text(encoding="ascii").strip()
    purged = purge_expired(
        actor="scheduled-retention-job", role="sales_engineer", key=key or None
    )
    print(f"Purged {len(purged)} expired prospect tenant(s).")


if __name__ == "__main__":
    main()
