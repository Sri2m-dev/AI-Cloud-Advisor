from data.supabase_client import supabase

res = supabase.table("organizations").select("*").execute()

print(res.data)

