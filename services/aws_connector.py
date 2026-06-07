from datetime import datetime

# -----------------------
# SAFE IMPORTS
# -----------------------
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    AWS_AVAILABLE = True
except ImportError:
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception
    AWS_AVAILABLE = False


# -----------------------
# ASSUME ROLE
# -----------------------
def assume_role(role_arn: str, external_id: str, session_name: str = "CloudAdvisorSession"):
    """
    Assumes an AWS IAM Role and returns temporary credentials.
    """

    if not AWS_AVAILABLE:
        print("AWS SDK (boto3) not installed")
        return None

    try:
        sts_client = boto3.client("sts")

        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            ExternalId=external_id
        )

        credentials = response["Credentials"]

        return {
            "aws_access_key_id": credentials["AccessKeyId"],
            "aws_secret_access_key": credentials["SecretAccessKey"],
            "aws_session_token": credentials["SessionToken"],
            "expiration": credentials["Expiration"]
        }

    except NoCredentialsError as e:
        print(f"AWS base credentials not found: {e}")
        return None

    except ClientError as e:
        print(f"Error assuming role: {e}")
        return None

    except Exception as e:
        print(f"Unexpected AWS error: {e}")
        return None


# -----------------------
# COST EXPLORER CLIENT
# -----------------------
def get_cost_explorer_client(temp_creds: dict, region: str = "us-east-1"):
    """
    Returns a Cost Explorer client using temporary credentials.
    """
    if not AWS_AVAILABLE:
        return None

    try:
        # Create a real Cost Explorer client when boto3 is available and creds provided
        return boto3.client(
            "ce",
            aws_access_key_id=temp_creds.get("aws_access_key_id"),
            aws_secret_access_key=temp_creds.get("aws_secret_access_key"),
            aws_session_token=temp_creds.get("aws_session_token"),
            region_name=region,
        )
    except Exception as e:
        print(f"Error creating Cost Explorer client: {e}")
        return None


# -----------------------
# OPTIONAL: GET AWS COST (HELPFUL FOR YOU)
# -----------------------
def get_aws_cost(temp_creds: dict, days: int = 30):
    """
    Fetch AWS cost data (safe version).
    """

    if not AWS_AVAILABLE:
        return []

    client = get_cost_explorer_client(temp_creds)
    if not client:
        return []

    from datetime import datetime, timedelta

    try:
        end = datetime.utcnow().date()
        start = end - timedelta(days=days)

        response = client.get_cost_and_usage(
            TimePeriod={
                "Start": start.strftime("%Y-%m-%d"),
                "End": end.strftime("%Y-%m-%d"),
            },
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"}
            ],
        )

        results = []

        for day in response.get("ResultsByTime", []):
            date = day["TimePeriod"]["Start"]

            for group in day.get("Groups", []):
                service = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])

                results.append({
                    "date": date,
                    "Service": service,
                    "Cost": cost
                })

        return results

    except Exception as e:
        print(f"AWS cost fetch error: {e}")
        return []


# -----------------------
# PHASE 1: AWS CUR + ATHENA READY DATA
# -----------------------
def _mock_athena_payload():
    return {
        "last_updated": "2026-04-11T09:00:00",
        "source": "AWS CUR / Athena mock response",
        "total_spend": 52000,
        "previous_spend": 47000,
        "services": [
            {
                "name": "EC2",
                "cost": 25000,
                "savings": 5200,
                "cloud": "AWS",
                "date": "2026-04-11",
                "resources": [
                    {
                        "id": "i-aws-101",
                        "type": "m6i.large",
                        "utilization": 27,
                        "waste": 650,
                    },
                    {
                        "id": "i-aws-202",
                        "type": "c6i.xlarge",
                        "utilization": 41,
                        "waste": 320,
                    },
                ],
            },
            {
                "name": "S3",
                "cost": 8000,
                "savings": 900,
                "cloud": "AWS",
                "date": "2026-04-11",
                "resources": [
                    {
                        "id": "s3-logs",
                        "type": "Standard",
                        "utilization": 52,
                        "waste": 140,
                    }
                ],
            },
            {
                "name": "RDS",
                "cost": 12000,
                "savings": 2400,
                "cloud": "AWS",
                "date": "2026-04-11",
                "resources": [
                    {
                        "id": "rds-prod-1",
                        "type": "db.r6g.large",
                        "utilization": 29,
                        "waste": 480,
                    }
                ],
            },
            {
                "name": "Lambda",
                "cost": 7000,
                "savings": 700,
                "cloud": "AWS",
                "date": "2026-04-11",
                "resources": [
                    {
                        "id": "lambda-finops",
                        "type": "Serverless",
                        "utilization": 38,
                        "waste": 110,
                    }
                ],
            },
        ],
        "actions": [
            {
                "id": "AWS1",
                "title": "Right-size EC2 fleet",
                "service": "EC2",
                "status": "In Progress",
                "estimated_savings": 5200,
                "realized_savings": 1200,
                "priority": "P1 • Savings",
                "owner": "CloudOps",
            },
            {
                "id": "AWS2",
                "title": "Archive cold S3 data",
                "service": "S3",
                "status": "Not Started",
                "estimated_savings": 900,
                "realized_savings": 0,
                "priority": "P2 • Efficiency",
                "owner": "Platform Engineering",
            },
        ],
    }


def _build_cur_query(table_name: str) -> str:
    return f"""
    SELECT
        COALESCE(product_product_name, 'Other') AS service_name,
        ROUND(SUM(CAST(line_item_blended_cost AS DOUBLE)), 2) AS total_cost
    FROM {table_name}
    WHERE CAST(line_item_usage_start_date AS TIMESTAMP)
        >= date_trunc('month', current_timestamp)
    GROUP BY 1
    ORDER BY total_cost DESC
    """.strip()


def _map_athena_rows_to_payload(rows):
    services = []
    for row in rows:
        service_name = str(row.get("service_name") or row.get("name") or "Other")
        total_cost = float(row.get("total_cost", 0) or 0)
        services.append(
            {
                "name": service_name,
                "cost": total_cost,
                "savings": round(total_cost * 0.12, 2),
                "cloud": "AWS",
                "date": datetime.utcnow().date().isoformat(),
                "resources": [],
            }
        )

    total_spend = sum(service["cost"] for service in services)
    return {
        "last_updated": datetime.utcnow().isoformat(timespec="seconds"),
        "source": "AWS CUR + Athena",
        "total_spend": total_spend,
        "previous_spend": round(total_spend * 0.9, 2),
        "services": services,
        "actions": [],
    }


def _load_cost_data_from_athena():
    import os
    import time

    database = os.getenv("AWS_ATHENA_DATABASE", "").strip()
    table_name = os.getenv("AWS_CUR_TABLE", "").strip()
    output_location = os.getenv("AWS_ATHENA_OUTPUT_LOCATION", "").strip()
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1").strip() or "us-east-1"

    if not AWS_AVAILABLE:
        raise RuntimeError("boto3 is not installed for Athena access")
    if not database or not table_name or not output_location:
        raise RuntimeError(
            "AWS CUR/Athena is not configured. Set AWS_ATHENA_DATABASE, "
            "AWS_CUR_TABLE, and AWS_ATHENA_OUTPUT_LOCATION."
        )

    athena_client = boto3.client("athena", region_name=region)
    query = _build_cur_query(table_name)
    response = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output_location},
    )
    execution_id = response["QueryExecutionId"]

    for _ in range(20):
        status_response = athena_client.get_query_execution(
            QueryExecutionId=execution_id
        )
        state = (
            status_response.get("QueryExecution", {})
            .get("Status", {})
            .get("State", "")
        )
        if state == "SUCCEEDED":
            break
        if state in {"FAILED", "CANCELLED"}:
            reason = (
                status_response.get("QueryExecution", {})
                .get("Status", {})
                .get("StateChangeReason", "Unknown Athena failure")
            )
            raise RuntimeError(f"Athena query failed: {reason}")
        time.sleep(1)
    else:
        raise RuntimeError("Athena query timed out")

    results = athena_client.get_query_results(QueryExecutionId=execution_id)
    result_rows = results.get("ResultSet", {}).get("Rows", [])
    parsed_rows = []
    for row in result_rows[1:]:
        values = [item.get("VarCharValue", "") for item in row.get("Data", [])]
        if len(values) >= 2:
            parsed_rows.append(
                {
                    "service_name": values[0],
                    "total_cost": float(values[1] or 0),
                }
            )

    return _map_athena_rows_to_payload(parsed_rows)


def get_cost_data():
    """Return AWS-shaped cost data, using CUR/Athena when configured."""
    import os

    force_failure = os.getenv("TEST_FORCE_AWS_FAILURE", "").strip().lower()
    if force_failure in {"1", "true", "yes"}:
        raise RuntimeError("AWS failure")

    athena_enabled = os.getenv("AWS_USE_ATHENA", "").strip().lower()
    if athena_enabled in {"1", "true", "yes"}:
        return _load_cost_data_from_athena()

    return _mock_athena_payload()

