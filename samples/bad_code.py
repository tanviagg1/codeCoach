"""
bad_code.py — Sample code with intentional issues for testing CodeCoach AI.

This file contains real problems that a senior engineer would flag:
- Hardcoded secrets
- SQL injection vulnerability
- No input validation
- Swallowed exceptions
- Poor naming
- Nested loops (O(n^2))
- Dead code

Use this to verify that ReviewAgent catches the right issues.
"""

import sqlite3
import os

# ISSUE: Hardcoded API key — should use environment variable
SECRET_KEY = "sk-super-secret-key-1234567890"
DB_PASSWORD = "admin123"

# ISSUE: No input validation on any of these parameters
def get_user(user_id, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # ISSUE: SQL injection — user_id is not sanitized
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cursor.execute(query)
    result = cursor.fetchone()
    conn.close()
    return result


def process_orders(orders, products):
    results = []
    # ISSUE: O(n^2) — nested loop where a dict lookup would work
    for order in orders:
        for product in products:
            if order["product_id"] == product["id"]:
                results.append({
                    "order_id": order["id"],
                    "product_name": product["name"],
                    "total": order["qty"] * product["price"]
                })
    return results


def save_report(data, filename):
    try:
        with open(filename, "w") as f:
            f.write(str(data))
    except:
        # ISSUE: Bare except swallows ALL exceptions including KeyboardInterrupt
        pass


# ISSUE: Dead code — this function is never called anywhere
def _old_format_user(u):
    return u["name"] + " " + u["email"]


# ISSUE: Poor naming — x, y, z tell us nothing
def calculate(x, y, z):
    a = x * y
    b = a + z
    # ISSUE: Magic number — what is 1.08? (sales tax? some ratio?)
    return b * 1.08


def authenticate(username, password):
    # ISSUE: Comparing password in plaintext — should use bcrypt/argon2
    if password == DB_PASSWORD:
        return True
    # ISSUE: Missing else — implicitly returns None, not False
