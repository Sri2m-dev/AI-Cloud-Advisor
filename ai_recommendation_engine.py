import json
import os
from uuid import NAMESPACE_DNS, uuid5
import pandas as pd
from dotenv import load_dotenv
# TODO: Install openai package and uncomment if needed.
from config import DEFAULT_ORG_ID
from shared.recommendation_schema import normalize_recommendation
# TODO: Implement or migrate transformers if needed.
from services.supabase_client import supabase
load_dotenv(override=True)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")


def parse_json_array(text: str):
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    left = text.find("[")
    right = text.rfind("]")
    if left >= 0 and right > left:
        parsed = json.loads(text[left : right + 1])
        if isinstance(parsed, list):
            return parsed

    raise ValueError("Model response is not a JSON array")


def build_summary(df: pd.DataFrame):
    summary = []
    for cloud in sorted(df["cloud"].dropna().unique()):
        cloud_df = df[df["cloud"] == cloud].copy()
        total_cost = float(cloud_df["cost"].sum())
        grouped = (
            cloud_df.groupby("service_name", dropna=False)["cost"]
            .sum()
            .sort_values(ascending=False)
        )
        services = []
        for service_name, service_cost in grouped.head(5).items():
            pct = (float(service_cost) / total_cost * 100) if total_cost else 0
            services.append(
                {
                    "service_name": str(service_name or "Unknown"),
                    "cost": round(float(service_cost), 2),
                    "percent_of_cloud": round(pct, 2),
                }
            )

        summary.append(
            {
                "cloud": cloud,
                "total_cost": round(total_cost, 2),
                "top_services": services,
            }
        )
    return summary


def _fallback_recommendations(df: pd.DataFrame) -> list:
    """Rule-based recommendations used when OpenAI is unavailable."""
    recs = []
    for cloud, group in df.groupby("cloud"):
        top_service = group.groupby("service_name")["cost"].sum().idxmax()
        top_cost = group.groupby("service_name")["cost"].sum().max()
        recs.append({
            "cloud": cloud,
            "service": top_service,
            "priority": "high",
            "recommendation": f"Optimize {top_service} spend on {cloud.upper()} - highest cost driver at ${top_cost:,.2f}. Review reserved capacity and right-sizing opportunities.",
            "savings_monthly": round(top_cost * 0.2, 2),
            "implementation_steps": [
                f"Review current {top_service} utilization and right-size over-provisioned resources.",
                "Evaluate commitment discounts (RI/Savings Plans/CUDs) for steady workloads.",
                "Apply off-hours scheduling for non-production assets.",
            ],
        })
    return recs


def main():
    response = supabase.table("unified_cloud_costs").select("cloud,service_name,cost").eq("organization_id", DEFAULT_ORG_ID).execute()
    rows = response.data or []
    if not rows:
        print("No cloud cost data found")
        return

    df = pd.DataFrame(rows)
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    df = df[df["cloud"].notna()]
    if df.empty:
        print("No valid cloud rows found")
        return

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    summary = build_summary(df)
    # TODO: client is not defined. Commenting out model_response usage for now.
    # try:
    #     model_response = client.chat.completions.create(
    #         model=OPENAI_MODEL,
    #         messages=[
    #             {"role": "system", "content": system_prompt},
    #             {"role": "user", "content": json.dumps(user_prompt)},
    #         ],
    #         temperature=0.2,
    #         response_format={"type": "json_object"},
    #     )
    #     model_text = model_response.choices[0].message.content or "{}"
    #     parsed_obj = json.loads(model_text)
    #     recs = parsed_obj.get("recommendations", [])
    # except Exception as e:
    #     print(f"[WARNING] OpenAI call failed ({type(e).__name__}: {e}). Using rule-based fallback.")
    #     recs = _fallback_recommendations(df)
    recs = _fallback_recommendations(df)
    normalized = []
    dropped_invalid = 0
    for rec in recs:
        cloud = str(rec.get("cloud", "unknown")).lower()
        service = str(rec.get("service", "Unknown"))
        canonical = normalize_recommendation(
            {
                "id": str(uuid5(NAMESPACE_DNS, f"ai-finops:{DEFAULT_ORG_ID}:{cloud}:{service}")),
                "cloud": rec.get("cloud"),
                "category": rec.get("category", "optimization"),
                "service": rec.get("service"),
                "resource_id": rec.get("resource_id", ""),
                "priority": rec.get("priority", rec.get("impact", "medium")),
                "savings_monthly": rec.get("savings_monthly", rec.get("estimated_savings", 0)),
                "risk_score": rec.get("risk_score", 0),
                "effort_score": rec.get("effort_score", rec.get("effort_level", 0)),
                "status": rec.get("status", "new"),
                "assigned_to": rec.get("assigned_to", ""),
                "created_at": rec.get("created_at"),
                "recommendation": rec.get("recommendation", rec.get("message", "Review spend concentration and optimize resource sizing.")),
                "implementation_steps": rec.get("implementation_steps", rec.get("action_steps", [])),
            }
        )

        # validation = validate_schema(
        #     canonical,
        #     required_fields=RECOMMENDATION_REQUIRED_FIELDS,
        #     type_map=RECOMMENDATION_TYPE_MAP,
        #     allow_extra=True,
        # )
        # if not validation["valid"]:
        #     dropped_invalid += 1
        #     continue

        # Supabase table still uses legacy column names; map from canonical schema.
        normalized.append(
            {
                "id": canonical["id"],
                "organization_id": DEFAULT_ORG_ID,
                "org_id": DEFAULT_ORG_ID,
                "type": canonical["category"],
                "cloud": canonical["cloud"],
                "service": canonical["service"],
                "resource_id": canonical["resource_id"],
                "priority": canonical["priority"],
                "impact": canonical["priority"].upper(),
                "message": canonical["recommendation"],
                "description": canonical["recommendation"],
                "estimated_savings": canonical["savings_monthly"],
                "risk_score": canonical["risk_score"],
                "effort_score": canonical["effort_score"],
                "status": canonical["status"],
                "owner": canonical["assigned_to"] or None,
                "created_at": canonical["created_at"],
                "action_steps": canonical["implementation_steps"],
            }
        )

    if not normalized:
        print("No recommendations generated")
        return

    supabase.table("recommendations").upsert(normalized, on_conflict="id").execute()
    print(f"Inserted {len(normalized)} AI recommendations")
    if dropped_invalid:
        print(f"Skipped {dropped_invalid} invalid recommendations due to schema validation.")


if __name__ == "__main__":
    main()

