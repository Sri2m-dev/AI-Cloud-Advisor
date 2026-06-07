from services.executive_dashboard_v2_service import (
    ExecutiveDashboardV2Service
)

data = ExecutiveDashboardV2Service.get_dashboard_data()

print("\nSUMMARY")
print(data["summary"])

print("\nBUDGET")
print(data["budget"][:3])

print("\nFORECAST")
print(data["forecast"][:3])

print("\nSAVINGS")
print(data["savings"])