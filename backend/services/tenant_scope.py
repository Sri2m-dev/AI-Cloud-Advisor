from supabase import Client


def scoped_query(
    client: Client,
    table_name: str,
    tenant_id: str,
):
    return (
        client
        .table(table_name)
        .select("*")
        .eq("organization_id", tenant_id)
    )
