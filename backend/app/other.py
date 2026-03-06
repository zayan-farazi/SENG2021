from supabase import create_client, Client
import datetime

SUPABASE_URL='https://zfkanfxuznozqpqfxbly.supabase.co'
SUPABASE_KEY='sb_publishable_jhMhN4VwzVrroJ202_ahAA_pChVwwnZ'

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# creates dictionary with table names and query information saved.
def defineQuery(buyerName, sellerName, deliveryStreet, 
                     deliveryCity, deliveryPostcode, deliveryCountry, notes,
                     timeIssued, status):
    return {'buyername': buyerName, 
       'sellername': sellerName,
       'deliverystreet': deliveryStreet,
       'deliverycity': deliveryCity,
       'deliverypostcode': deliveryPostcode,
       'deliverycountry': deliveryCountry,
       'timeIssued': timeIssued,
       'lastedited': timeIssued,
       'status': timeIssued,
       'notes': notes
    }

# saves order information as new entry 
def saveOrder(buyerName, sellerName, deliveryStreet, 
                     deliveryCity, deliveryPostcode, deliveryCountry, notes,
                     timeIssued=datetime.now(), status='Pending'):
    
    query = defineQuery(buyerName, sellerName, deliveryStreet, 
                     deliveryCity, deliveryPostcode, deliveryCountry, notes,
                     timeIssued, status)
    supabase.table('orders').insert(query).execute()

# Input only the necessary fields
# Returns all orders with given filters, NULL if no order matches the filters
def retrieveOrder(buyerName='*', sellerName='*', deliveryStreet='*', 
                     deliveryCity='*', deliveryPostcode='*', deliveryCountry='*', notes='*',
                     timeIssued='*', status='*'):
    query= query = defineQuery(buyerName, sellerName, deliveryStreet, 
                     deliveryCity, deliveryPostcode, deliveryCountry, notes,
                     timeIssued, status)
    supabase.table('orders').select('*').eq(query):

# saves order detail information
# MUST BE ENTERED ONE LINE AT A TIME
def saveOrderDetails()