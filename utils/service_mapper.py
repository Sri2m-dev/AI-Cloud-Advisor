SERVICE_CATEGORY_MAP = {

    # Compute
    "AmazonEC2": "Compute",
    "Elastic Compute Cloud": "Compute",
    "Virtual Machines": "Compute",
    "Compute Engine": "Compute",

    # Storage
    "Simple Storage Service": "Storage",
    "AmazonS3": "Storage",
    "Storage": "Storage",
    "Elastic File System": "Storage",
    "S3 Glacier Deep Archive": "Storage",

    # Database
    "Relational Database Service": "Database",
    "AmazonRDS": "Database",
    "Redshift": "Database",
    "ElastiCache": "Database",

    # Networking
    "Virtual Private Cloud": "Networking",
    "AmazonVPC": "Networking",
    "Data Transfer": "Networking",
    "Elastic Load Balancing": "Networking",
    "API Gateway": "Networking",

    # Security
    "GuardDuty": "Security",
    "Inspector": "Security",
    "Security Hub": "Security",
    "Key Management Service": "Security",
    "Secrets Manager": "Security",
    "Cognito": "Security",

    # Monitoring
    "AmazonCloudWatch": "Monitoring",
    "CloudWatch Events": "Monitoring",

    # Containers
    "Elastic Container Service for Kubernetes": "Containers",
    "EC2 Container Registry (ECR)": "Containers",
    "Managed Streaming for Apache Kafka": "Containers",

    # Analytics
    "Athena": "Analytics",
    "QuickSight": "Analytics",

    # AI/ML
    "Claude 3 Sonnet (Bedrock Edition)": "AI/ML",
    "Textract": "AI/ML",
    "SageMaker": "AI/ML",

    # Management
    "Config": "Management",
    "Backup": "Management",
    "Cost Explorer": "Management",
    "DevOps Guru": "Management",

    # Misc
    "Glue": "Integration",
    "Lambda": "Serverless",
    "WAF": "Security",
    "X-Ray": "Monitoring"
}


def get_service_category(service_name):
    return SERVICE_CATEGORY_MAP.get(service_name, "Other")