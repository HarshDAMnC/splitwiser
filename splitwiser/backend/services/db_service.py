import uuid
from datetime import datetime
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.supabase_client import get_db

class MockDB:
    """Fallback in-memory DB if Supabase is not configured."""
    def __init__(self):
        self.collections = {
            'users': {}, 'groups': {}, 'group_members': {},
            'categories': {}, 'expenses': {}, 'expense_payers': {},
            'expense_splits': {}, 'transactions': {}, 'settlements': {},
            'user_balances_cache': {}
        }

    def set(self, col, doc_id, data):
        self.collections[col][doc_id] = data

    def query(self, col, key, val):
        return [doc for doc in self.collections[col].values() if doc.get(key) == val]

    def get_all(self, col):
        return list(self.collections[col].values())

    def delete(self, col, doc_id):
        if doc_id in self.collections[col]:
            del self.collections[col][doc_id]
            return True
        return False

    def delete_where(self, col, key, val):
        to_del = [k for k, v in self.collections[col].items() if v.get(key) == val]
        for k in to_del:
            del self.collections[col][k]
        return len(to_del)

mock_db = MockDB()

def get_db_client():
    db = get_db()
    is_mock = (db == "MOCK_DB_MISSING_KEY")
    return db, is_mock

# Property for backwards compatibility
@property
def is_mock():
    _, mock_flag = get_db_client()
    return mock_flag

def generate_id():
    return str(uuid.uuid4())

def now():
    return datetime.utcnow().isoformat()

def insert_doc(table, data):
    db, mock_flag = get_db_client()
    if mock_flag:
        doc_id = data.get('id')
        if not doc_id:
            doc_id = generate_id()
            data['id'] = doc_id
        mock_db.set(table, doc_id, data)
        return doc_id
    else:
        response = db.table(table).insert(data).execute()
        return response.data[0]['id']

def create_user(name, email):
    uid = generate_id()
    insert_doc('users', {
        'id': uid,
        'name': name,
        'email': email,
        'created_at': now()
    })
    return uid

def create_group(name, description, creator_id):
    gid = generate_id()
    insert_doc('groups', {
        'id': gid,
        'name': name,
        'description': description,
        'created_by': creator_id,
        'created_at': now()
    })
    if creator_id:
        add_group_member(gid, creator_id)
    return gid

def add_group_member(group_id, user_id):
    db, mock_flag = get_db_client()
    if mock_flag:
        existing = [d for d in mock_db.query('group_members', 'group_id', group_id) if d.get('user_id') == user_id]
        if existing:
            return existing[0]['id']
    else:
        resp = db.table('group_members').select('id').eq('group_id', group_id).eq('user_id', user_id).execute()
        if resp.data:
            return resp.data[0]['id']
    
    mid = generate_id()
    insert_doc('group_members', {
        'id': mid,
        'group_id': group_id,
        'user_id': user_id,
        'joined_at': now()
    })
    return mid

def update_balance_cache(group_id, user_id, amount_change):
    db, mock_flag = get_db_client()
    if mock_flag:
        docs = mock_db.query('user_balances_cache', 'user_id', user_id)
        docs = [d for d in docs if d.get('group_id') == group_id]
        if docs:
            doc = docs[0]
            doc['net_balance'] += amount_change
        else:
            insert_doc('user_balances_cache', {
                'id': generate_id(),
                'group_id': group_id,
                'user_id': user_id,
                'net_balance': amount_change
            })
    else:
        response = db.table('user_balances_cache').select('*').eq('group_id', group_id).eq('user_id', user_id).execute()
        if len(response.data) > 0:
            doc = response.data[0]
            new_bal = float(doc['net_balance']) + amount_change
            db.table('user_balances_cache').update({'net_balance': new_bal}).eq('id', doc['id']).execute()
        else:
            insert_doc('user_balances_cache', {
                'id': generate_id(),
                'group_id': group_id,
                'user_id': user_id,
                'net_balance': amount_change
            })

def add_expense(group_id, description, category_id, total_amount, created_by, payers, splits):
    eid = generate_id()
    insert_doc('expenses', {
        'id': eid,
        'group_id': group_id,
        'category_id': category_id,
        'description': description,
        'total_amount': total_amount,
        'created_by': created_by,
        'created_at': now()
    })
    
    for u_id, amt in payers.items():
        if amt > 0:
            insert_doc('expense_payers', {
                'id': generate_id(),
                'expense_id': eid,
                'user_id': u_id,
                'amount_paid': amt
            })
            update_balance_cache(group_id, u_id, amt)
            
    for u_id, amt in splits.items():
        if amt > 0:
            insert_doc('expense_splits', {
                'id': generate_id(),
                'expense_id': eid,
                'user_id': u_id,
                'amount_owed': amt
            })
            update_balance_cache(group_id, u_id, -amt)
            
    return eid

def get_group_balances(group_id):
    db, mock_flag = get_db_client()
    balances = {}
    if mock_flag:
        docs = mock_db.query('user_balances_cache', 'group_id', group_id)
        for doc in docs:
            balances[doc['user_id']] = doc['net_balance']
    else:
        response = db.table('user_balances_cache').select('user_id, net_balance').eq('group_id', group_id).execute()
        for doc in response.data:
            balances[doc['user_id']] = float(doc['net_balance'])
    return balances

def save_simplified_graph(group_id, transactions_list):
    db, mock_flag = get_db_client()
    if mock_flag: return
    
    db.table('transactions').delete().eq('group_id', group_id).eq('type', 'SYSTEM_GENERATED_DEBT').execute()
    
    for debtor, creditor, amt in transactions_list:
        insert_doc('transactions', {
            'id': generate_id(),
            'group_id': group_id,
            'from_user_id': debtor,
            'to_user_id': creditor,
            'amount': amt,
            'type': 'SYSTEM_GENERATED_DEBT',
            'created_at': now()
        })

def add_settlement(group_id, from_user, to_user, amount):
    insert_doc('settlements', {
        'id': generate_id(),
        'from_user_id': from_user,
        'to_user_id': to_user,
        'amount': amount,
        'group_id': group_id,
        'status': 'COMPLETED',
        'settled_at': now()
    })
    
    update_balance_cache(group_id, from_user, amount)
    update_balance_cache(group_id, to_user, -amount)

def get_users():
    db, mock_flag = get_db_client()
    if mock_flag:
        return mock_db.get_all('users')
    response = db.table('users').select('*').execute()
    return response.data

def get_groups():
    db, mock_flag = get_db_client()
    if mock_flag:
        return mock_db.get_all('groups')
    response = db.table('groups').select('*').execute()
    return response.data

def get_expenses(group_id):
    db, mock_flag = get_db_client()
    if mock_flag:
        return mock_db.query('expenses', 'group_id', group_id)
    response = db.table('expenses').select('*').eq('group_id', group_id).execute()
    return sorted(response.data, key=lambda x: x.get('created_at', ''), reverse=True)

# ===========================
# DELETE OPERATIONS
# ===========================

def delete_user(user_id):
    db, mock_flag = get_db_client()
    if mock_flag:
        mock_db.delete('users', user_id)
        mock_db.delete_where('group_members', 'user_id', user_id)
        mock_db.delete_where('user_balances_cache', 'user_id', user_id)
        return True
    else:
        db.table('user_balances_cache').delete().eq('user_id', user_id).execute()
        db.table('group_members').delete().eq('user_id', user_id).execute()
        db.table('expense_payers').delete().eq('user_id', user_id).execute()
        db.table('expense_splits').delete().eq('user_id', user_id).execute()
        db.table('settlements').delete().eq('from_user_id', user_id).execute()
        db.table('settlements').delete().eq('to_user_id', user_id).execute()
        db.table('transactions').delete().eq('from_user_id', user_id).execute()
        db.table('transactions').delete().eq('to_user_id', user_id).execute()
        db.table('users').delete().eq('id', user_id).execute()
        return True

def delete_group(group_id):
    db, mock_flag = get_db_client()
    if mock_flag:
        mock_db.delete('groups', group_id)
        mock_db.delete_where('group_members', 'group_id', group_id)
        mock_db.delete_where('expenses', 'group_id', group_id)
        mock_db.delete_where('user_balances_cache', 'group_id', group_id)
        mock_db.delete_where('transactions', 'group_id', group_id)
        mock_db.delete_where('settlements', 'group_id', group_id)
        return True
    else:
        db.table('user_balances_cache').delete().eq('group_id', group_id).execute()
        db.table('settlements').delete().eq('group_id', group_id).execute()
        db.table('transactions').delete().eq('group_id', group_id).execute()
        db.table('expenses').delete().eq('group_id', group_id).execute()
        db.table('group_members').delete().eq('group_id', group_id).execute()
        db.table('groups').delete().eq('id', group_id).execute()
        return True

def delete_expense(expense_id, group_id):
    db, mock_flag = get_db_client()
    if mock_flag:
        payers = [d for d in mock_db.get_all('expense_payers') if d.get('expense_id') == expense_id]
        splits = [d for d in mock_db.get_all('expense_splits') if d.get('expense_id') == expense_id]
    else:
        payers = db.table('expense_payers').select('*').eq('expense_id', expense_id).execute().data
        splits = db.table('expense_splits').select('*').eq('expense_id', expense_id).execute().data

    for p in payers:
        update_balance_cache(group_id, p['user_id'], -float(p['amount_paid']))
    
    for s in splits:
        update_balance_cache(group_id, s['user_id'], float(s['amount_owed']))
    
    if mock_flag:
        mock_db.delete('expenses', expense_id)
        mock_db.delete_where('expense_payers', 'expense_id', expense_id)
        mock_db.delete_where('expense_splits', 'expense_id', expense_id)
    else:
        db.table('expense_payers').delete().eq('expense_id', expense_id).execute()
        db.table('expense_splits').delete().eq('expense_id', expense_id).execute()
        db.table('expenses').delete().eq('id', expense_id).execute()
    
    return True

def get_group_members(group_id):
    db, mock_flag = get_db_client()
    if mock_flag:
        member_docs = mock_db.query('group_members', 'group_id', group_id)
        member_ids = [m['user_id'] for m in member_docs]
        all_users = mock_db.get_all('users')
        return [u for u in all_users if u['id'] in member_ids]
    else:
        members = db.table('group_members').select('user_id').eq('group_id', group_id).execute().data
        member_ids = [m['user_id'] for m in members]
        if not member_ids:
            return []
        result = []
        for uid in member_ids:
            user = db.table('users').select('*').eq('id', uid).execute().data
            if user:
                result.append(user[0])
        return result

def settle_all(group_id):
    from backend.services.graph_algo import simplify_debts
    balances = get_group_balances(group_id)
    transactions = simplify_debts(balances)
    for debtor, creditor, amt in transactions:
        add_settlement(group_id, debtor, creditor, amt)
    save_simplified_graph(group_id, [])
    return transactions
