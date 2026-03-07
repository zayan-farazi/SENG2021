from supabase import create_client, Client
import datetime

SUPABASE_URL='https://zfkanfxuznozqpqfxbly.supabase.co'
SUPABASE_KEY='sb_publishable_jhMhN4VwzVrroJ202_ahAA_pChVwwnZ'

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# saves order information and returns order Id
def saveOrder(buyername, sellername, deliverystreet, deliverycity,
              deliverypostcode, deliverycountry, notes,
              issueDate=None, status='Pending'):
    
    if issueDate is None:
        issueDate = datetime.datetime.now()

    query = {
        'buyername': buyername,
        'sellername': sellername,
        'deliverystreet': deliverystreet,
        'deliverycity': deliverycity,
        'deliverypostcode': deliverypostcode,
        'deliverycountry': deliverycountry,
        'status': status,
        'notes': notes,
        'issuedate': issueDate.isoformat(),
        'lastchanged': datetime.datetime.now().isoformat()
    }

    try:
        response = supabase.table('orders').insert(query).execute()
        return response.data[0]['id']
    except Exception as e:
        raise RuntimeError(f"Failed to save order: {e}")

# saves a single line of order details, does not return anything
def saveOrderDetails(orderId, productName, unitCode, quantity, unitPrice):
    if orderId is None:
        raise ValueError("Failed to parse order details: orderId can\'t be empty")
    
    query = {
        'orderid': orderId,
        'productname': productName,
        'unitcode': unitCode,
        'quantity': quantity,
        'unitprice': unitPrice
    }

    try:
       supabase.table('orderdetails').insert(query).execute()
    except Exception as e:
       raise RuntimeError(f"Failed to save order details: {e}")

# (greedily) returns all tuples mathing the filter(s). 
# must write the variable name as all fields have empty default values
def findOrders(buyername=None, sellername=None, deliverystreet=None, deliverycity=None,
              deliverypostcode=None, deliverycountry=None, notes=None,
              issueDate=None, lastChanged=None, status=None):
    query = supabase.table('orders').select('*')

    if buyername:    
        query = query.eq('buyername', buyername)
    if sellername:   
        query = query.eq('sellername', sellername)
    if deliverystreet:      
        query = query.eq('deliverystreet', deliverystreet)
    if deliverycity: 
        query = query.eq('deliverycity', deliverycity)
    if deliverypostcode:    
        query = query.eq('deliverypostcode', deliverypostcode)
    if deliverycountry:     
        query = query.eq('deliverycountry', deliverycountry)
    if notes: 
        query = query.ilike('notes', notes)
    if status:       
        query = query.eq('status', status)
    if issueDate:    
        query = query.eq('issuedate', issueDate)
    if lastChanged:  
        query = query.eq('lastchanged', lastChanged)
    if status:       
        query = query.eq('status', status)

    return query.execute()
