"""
good_code.py — Sample code with clean practices for testing CodeCoach AI.

This file demonstrates what well-written Python looks like:
- Environment variables for secrets
- Parameterized queries (no SQL injection)
- Input validation
- Proper error handling
- Descriptive naming
- Efficient algorithms
- Clear documentation

Use this to verify that ReviewAgent does NOT flag false positives.
"""

import os
import sqlite3
import bcrypt
from typing import Optional


def get_user(user_id: int, db_path: str) -> Optional[dict]:
    """
    Fetch a user by ID from the database.

    Args:
        user_id: The user's integer ID. Must be a positive integer.
        db_path: Path to the SQLite database file.

    Returns:
        A dict with user fields, or None if not found.

    Raises:
        ValueError: If user_id is not a positive integer.
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"user_id must be a positive integer, got: {user_id!r}")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        # Parameterized query prevents SQL injection
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def process_orders(orders: list[dict], products: list[dict]) -> list[dict]:
    """
    Join orders with their product details.

    Uses a dict lookup (O(n)) instead of nested loops (O(n^2)).

    Args:
        orders: List of order dicts with keys: id, product_id, qty
        products: List of product dicts with keys: id, name, price

    Returns:
        List of enriched order dicts with product_name and total.
    """
    # Build a product lookup dict once — O(n) instead of O(n^2)
    product_by_id = {p["id"]: p for p in products}

    results = []
    for order in orders:
        product = product_by_id.get(order["product_id"])
        if product is None:
            continue  # Skip orders with unknown products
        results.append({
            "order_id": order["id"],
            "product_name": product["name"],
            "total": order["qty"] * product["price"],
        })
    return results


def save_report(data: str, filepath: str) -> None:
    """
    Save a report string to a file.

    Args:
        data: The content to write.
        filepath: Destination file path.

    Raises:
        OSError: If the file cannot be written.
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(data)
    except OSError as e:
        # Re-raise with context — don't swallow the error
        raise OSError(f"Failed to write report to {filepath}: {e}") from e


SALES_TAX_RATE = 1.08  # Named constant — makes the magic number meaningful


def calculate_order_total(subtotal: float, quantity: int, discount: float = 0.0) -> float:
    """
    Calculate the final order total including tax and discount.

    Args:
        subtotal: Base price per unit.
        quantity: Number of units.
        discount: Discount amount to subtract (default 0).

    Returns:
        Final total after discount and tax.
    """
    pre_tax = (subtotal * quantity) - discount
    return pre_tax * SALES_TAX_RATE


def authenticate(username: str, password: str) -> bool:
    """
    Authenticate a user by checking their password hash.

    Uses bcrypt for secure password comparison.

    Args:
        username: The user's username.
        password: The plaintext password to verify.

    Returns:
        True if credentials are valid, False otherwise.
    """
    if not username or not password:
        return False

    # In a real app, fetch the hash from the database
    stored_hash = _get_password_hash(username)
    if stored_hash is None:
        return False  # User not found

    # bcrypt handles timing-safe comparison
    return bcrypt.checkpw(password.encode("utf-8"), stored_hash)


def _get_password_hash(username: str) -> Optional[bytes]:
    """Fetch the stored bcrypt hash for a username. Returns None if not found."""
    # In production: query database. Here: placeholder.
    raise NotImplementedError("Connect to your database in production.")
