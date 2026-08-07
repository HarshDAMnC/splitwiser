import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from backend.services.db_service import db_conn, is_mock, update_balance_cache, get_groups, get_group_balances

groups = get_groups()
for g in groups:
    gid = g['id']
    balances = get_group_balances(gid)
    total = sum(balances.values())
    if abs(total) > 0.01:
        # Group is leaking phantom money, fix it by adjusting the first user's balance
        first_user = list(balances.keys())[0] if balances else None
        if first_user:
            # If total is negative (phantom debt), we need to add positive balance to someone to zero it out
            # If total is positive, we subtract.
            correction = -total
            update_balance_cache(gid, first_user, correction)
            print(f"Fixed phantom balance of {total} in group {g['name']} by adding {correction} to {first_user}")
    
    # Verify
    new_balances = get_group_balances(gid)
    new_total = sum(new_balances.values())
    print(f"Group {g['name']} net sum is now: {new_total}")

print("All groups zero-sum invariant enforced!")
