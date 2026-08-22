import pytest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.graph_algo import simplify_debts

def test_single_debt_chain():
    # A owes B 10, B owes C 10 -> Net: A: -10, B: 0, C: 10
    balances = {'A': -10.0, 'B': 0.0, 'C': 10.0}
    transactions = simplify_debts(balances)
    assert len(transactions) == 1
    assert transactions[0] == ('A', 'C', 10.0)

def test_balanced_zero():
    # Everyone is settled up
    balances = {'A': 0.0, 'B': 0.0, 'C': 0.0}
    transactions = simplify_debts(balances)
    assert len(transactions) == 0

def test_complex_multi_user():
    # A: +50, B: +30, C: -40, D: -40
    balances = {'A': 50.0, 'B': 30.0, 'C': -40.0, 'D': -40.0}
    transactions = simplify_debts(balances)
    
    # Verify total settled amount matches net debts (80.0)
    total_transacted = sum(amt for _, _, amt in transactions)
    assert total_transacted == 80.0
    
    # Verify graph simplification reduces total edge count (<= 3 transactions)
    assert len(transactions) <= 3

def test_floating_precision():
    # Minor floating precision values near zero
    balances = {'A': 0.0001, 'B': -0.0001}
    transactions = simplify_debts(balances)
    assert len(transactions) == 0
