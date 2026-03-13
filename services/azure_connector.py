from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient

def get_azure_resource_groups(tenant_id, client_id, client_secret, subscription_id):
    """
    Authenticate with Azure and list resource groups.
    """
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    resource_client = ResourceManagementClient(credential, subscription_id)
    return [rg.name for rg in resource_client.resource_groups.list()]
