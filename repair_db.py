import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.services.db_service import db_conn, is_mock, update_balance_cache

# Fetch all groups
if is_mock:
    print("Using Mock DB. Cannot repair real Supabase.")
else:
    # Get all users and zero out their cache
    db_conn.table('user_balances_cache').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
    
    # Let's iterate over ALL expenses and settlements to rebuild the balance cache
    expenses = db_conn.table('expenses').select('*').execute().data
    for exp in expenses:
        group_id = exp['group_id']
        eid = exp['id']
        
        payers = db_conn.table('expense_payers').select('*').eq('expense_id', eid).execute().data
        for p in payers:
            update_balance_cache(group_id, p['user_id'], float(p['amount_paid']))
            
        splits = db_conn.table('expense_splits').select('*').eq('expense_id', eid).execute().data
        for s in splits:
            update_balance_cache(group_id, s['user_id'], -float(s['amount_owed']))
            
    settlements = db_conn.table('settlements').select('*').execute().data
    for sett in settlements:
        group_id = sett['group_id']
        update_balance_cache(group_id, sett['from_user_id'], float(sett['amount']))
        update_balance_cache(group_id, sett['to_user_id'], -float(sett['amount']))
        
    print("Balances successfully rebuilt from source of truth!")
