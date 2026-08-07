from flask import Flask, jsonify, request
from flask_cors import CORS
import sys
import os
from dotenv import load_dotenv

backend_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(backend_dir)
sys.path.append(project_dir)

load_dotenv(os.path.join(backend_dir, '.env'), override=True)

from backend.services.db_service import (
    create_user, create_group, add_group_member, add_expense, 
    get_group_balances, get_db_client, save_simplified_graph, add_settlement,
    delete_user, delete_group, delete_expense, get_group_members, settle_all
)
from backend.services.graph_algo import simplify_debts

app = Flask(__name__)
CORS(app)


@app.route('/health', methods=['GET'])
def health_check():
    _, mock_flag = get_db_client()
    return jsonify({"status": "ok", "db_mode": "mock" if mock_flag else "supabase"})


@app.route('/api/seed', methods=['POST'])
def api_seed():
    """Seeds the DB with test users, groups, and complex expenses, similar to the CLI tool."""
    u1 = create_user("Alice", "alice@test.com")
    u2 = create_user("Bob", "bob@test.com")
    u3 = create_user("Charlie", "charlie@test.com")
    u4 = create_user("David", "david@test.com")
    users = [u1, u2, u3, u4]
    
    g1 = create_group("Goa Trip 2026", "A tech bro trip", u1)
    for u in users[1:]:
        add_group_member(g1, u)
        
    # Dinner 100: A(50), B(50). Split: 25 all.
    add_expense(g1, "Dinner", None, 100.0, u1, {u1: 50.0, u2: 50.0}, {u1: 25.0, u2: 25.0, u3: 25.0, u4: 25.0})
    # Hotel 200: C(200). Split: B(100), D(100).
    add_expense(g1, "Hotel", None, 200.0, u3, {u3: 200.0}, {u2: 100.0, u4: 100.0})
    
    return jsonify({"group_id": g1, "users": users}), 201

@app.route('/api/users', methods=['POST', 'GET'])
def api_users():
    if request.method == 'GET':
        from backend.services.db_service import get_users
        return jsonify(get_users()), 200
        
    data = request.json
    uid = create_user(data.get('name'), data.get('email'))
    
    # Optionally add the user to a group
    group_id = data.get('group_id')
    if group_id:
        add_group_member(group_id, uid)
    
    return jsonify({"user_id": uid}), 201

@app.route('/api/users/<user_id>', methods=['DELETE'])
def api_delete_user(user_id):
    """Deletes a user and all associated data."""
    delete_user(user_id)
    return jsonify({"status": "user deleted"}), 200

@app.route('/api/groups', methods=['POST', 'GET'])
def api_groups():
    if request.method == 'GET':
        from backend.services.db_service import get_groups
        return jsonify(get_groups()), 200
        
    data = request.json
    gid = create_group(data.get('name'), data.get('description', ''), data.get('creator_id'))
    return jsonify({"group_id": gid}), 201

@app.route('/api/groups/<group_id>', methods=['DELETE'])
def api_delete_group(group_id):
    """Deletes a group and all associated data."""
    delete_group(group_id)
    return jsonify({"status": "group deleted"}), 200

@app.route('/api/groups/<group_id>/members', methods=['GET', 'POST'])
def api_group_members(group_id):
    """GET: list members. POST: add a user to the group."""
    if request.method == 'GET':
        members = get_group_members(group_id)
        return jsonify(members), 200
    
    data = request.json
    user_id = data.get('user_id')
    mid = add_group_member(group_id, user_id)
    return jsonify({"member_id": mid}), 201

@app.route('/api/expenses', methods=['POST'])
def api_add_expense():
    data = request.json
    eid = add_expense(
        data['group_id'], 
        data['description'], 
        data.get('category_id'), 
        data.get('total_amount', 0), 
        data['created_by'], 
        data['payers'], 
        data['splits']
    )
    return jsonify({"expense_id": eid}), 201

@app.route('/api/expenses/<expense_id>', methods=['DELETE'])
def api_delete_expense(expense_id):
    """Deletes an expense and reverses balance changes."""
    group_id = request.args.get('group_id')
    if not group_id:
        return jsonify({"error": "group_id query param required"}), 400
    delete_expense(expense_id, group_id)
    return jsonify({"status": "expense deleted"}), 200

@app.route('/api/groups/<group_id>/expenses', methods=['GET'])
def api_get_expenses(group_id):
    from backend.services.db_service import get_expenses
    return jsonify(get_expenses(group_id)), 200

@app.route('/api/groups/<group_id>/settle', methods=['GET'])
def api_settle_group(group_id):
    balances = get_group_balances(group_id)
    # Simplify debts
    transactions = simplify_debts(balances)
    
    # Silently cache this result immediately into the transactions table!
    save_simplified_graph(group_id, transactions)
    
    res = []
    for d, c, amt in transactions:
        res.append({
            "from": d,
            "to": c,
            "amount": amt
        })
    return jsonify({
        "net_balances": balances,
        "minimized_transactions": res
    })

@app.route('/api/groups/<group_id>/settle-all', methods=['POST'])
def api_settle_all(group_id):
    """Settles ALL outstanding debts in the group at once."""
    transactions = settle_all(group_id)
    res = []
    for d, c, amt in transactions:
        res.append({"from": d, "to": c, "amount": amt})
    return jsonify({"status": "all debts settled", "settlements": res}), 201

@app.route('/api/settlements', methods=['POST'])
def api_add_settlement():
    """Route payload: { group_id, from_user, to_user, amount }"""
    data = request.json
    add_settlement(data['group_id'], data['from_user'], data['to_user'], data['amount'])
    return jsonify({"status": "successfully settled"}), 201

if __name__ == '__main__':
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    app.run(host=host, port=5000, debug=True)

