import boto3


def stop_ec2_instance(instance_id, safe_mode=True):
    if safe_mode:
        return f"[SAFE MODE] Would stop instance {instance_id}"

    try:
        ec2 = boto3.client("ec2")
        ec2.stop_instances(InstanceIds=[instance_id])
        return f"Instance {instance_id} stopped successfully"
    except Exception as e:
        return f"Error: {str(e)}"


def resize_ec2_instance(instance_id, instance_type, safe_mode=True):
    if safe_mode:
        return f"[SAFE MODE] Would resize {instance_id} to {instance_type}"

    try:
        ec2 = boto3.client("ec2")
        ec2.stop_instances(InstanceIds=[instance_id])
        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={"Value": instance_type},
        )
        ec2.start_instances(InstanceIds=[instance_id])
        return f"Instance resized to {instance_type}"
    except Exception as e:
        return f"Error: {str(e)}"
