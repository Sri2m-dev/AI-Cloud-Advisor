from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.performance_service import PerformanceService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Nexora performance benchmark suite.")
    parser.add_argument("--organization-id", default="performance-benchmark", help="Organization id for scoped in-memory benchmark data.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()

    service = PerformanceService(args.organization_id)
    assessment = service.run_performance_assessment(persist=True)
    benchmarks = service.benchmark_major_modules(persist=True)
    payload = {
        "organization_id": args.organization_id,
        "performance_health": assessment["score"],
        "status": assessment["status"],
        "benchmarks": benchmarks,
        "targets": assessment["kpis"],
        "production_execution_enabled": False,
    }
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"Performance Health: {payload['performance_health']}% ({payload['status']})")
        for row in benchmarks:
            print(f"{row['Benchmark']}: {row['Duration Ms']} ms [{row['Status']}]")
        print("Production execution enabled: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
