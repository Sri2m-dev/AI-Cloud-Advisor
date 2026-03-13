import boto3
from botocore.exceptions import ClientError

def assume_role(role_arn: str, external_id: str, session_name: str = "CloudAdvisorSession"):
    """
    Assumes an AWS IAM Role and returns temporary credentials.
    """
    sts_client = boto3.client("sts")
    try:
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
    except ClientError as e:
        print(f"Error assuming role: {e}")
        return None

def get_cost_explorer_client(temp_creds: dict, region: str = "us-east-1"):
    """
    Returns a Cost Explorer client using temporary credentials.
    """
    return boto3.client(
        "ce",
        aws_access_key_id=temp_creds["aws_access_key_id"],
        aws_secret_access_key=temp_creds["aws_secret_access_key"],
        aws_session_token=temp_creds["aws_session_token"],
        region_name=region
    )
