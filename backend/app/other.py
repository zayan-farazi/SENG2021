from supabase import create_client, Client

SUPABASE_URL='https://zfkanfxuznozqpqfxbly.supabase.co'
SUPABASE_KEY='sb_publishable_jhMhN4VwzVrroJ202_ahAA_pChVwwnZ'

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

new = {'buyername': 'Jane Doe', 
       'sellername': 'John Doe',
       'deliverystreet': '221B Baker St',
       'deliverycity': 'Sydney',
       'deliverypostcode': '1234',
       'deliverycountry': 'Australia',
       'status': 'pending',
       'notes': 'boooop'}

supabase.table('orders').insert(new).execute()
results = supabase.table('orders').select('*').execute()
print(results)
