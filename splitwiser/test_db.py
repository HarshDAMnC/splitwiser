import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.services.db_service import get_users, get_groups, get_group_balances
from backend.services.graph_algo import simplify_debts

groups = get_groups()
print("Groups:", groups)
for g in groups:
    balances = get_group_balances(g['id'])
    print(f"Balances for {g['name']}: {balances}")
    print(f"Simplified debts: {simplify_debts(balances)}")
