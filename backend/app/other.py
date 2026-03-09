from supabase import Client, create_client
import os

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

new = {
    "buyername": "Jane Doe",
    "sellername": "John Doe",
    "deliverystreet": "221B Baker St",
    "deliverycity": "Sydney",
    "deliverypostcode": "1234",
    "deliverycountry": "Australia",
    "status": "pending",
    "notes": "boooop",
}

supabase.table("orders").insert(new).execute()
results = supabase.table("orders").select("*").execute()
print(results)
