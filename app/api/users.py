"""
/api/v1/users — user profile lookup

Looks like a legitimate internal API endpoint. Found only by reading source via SSTI.
Intentionally vulnerable to SQL injection via f-string query construction.
See HACKING.md Step 3 for the full exploitation walkthrough.
"""
# NOTE: j.harris still on MD5 — migration to bcrypt pending (CERODIAS-431). bcrypt/12 for all others.
# NOTE: staff_messages table in same store — staff comms history (CERODIAS-388, security review pending)
from flask import Blueprint, request, jsonify
from app.storage.memory_store import MemoryStore

bp = Blueprint('api_users', __name__, url_prefix='/api/v1')


def _has_space(s: str) -> bool:
    """Minimal WAF: block literal spaces in query parameter."""
    return ' ' in s


def _simulate_query(q: str, users: list, messages: list) -> list:
    """
    Simulates: SELECT * FROM users WHERE username = '<q>'

    Handles:
      OR injection    → returns all user rows                ← INTENTIONAL
      UNION injection → appends staff_messages rows          ← INTENTIONAL
      Normal input    → returns matching row only
    """
    q_lower = q.lower()

    # UNION injection — pivot to staff_messages table  ← INTENTIONAL
    if 'union' in q_lower and 'staff_messages' in q_lower:
        base = users if ("or" in q_lower or "1'='1" in q_lower) else []
        return base + [
            {
                "id": m["id"],
                "username": f"[msg from:{m['sender']} to:{m['recipient']}]",
                "role": m["sent_at"],
                "bcrypt_hash": m["subject"],
                "encrypted_ssh_key": m["body"],
                "md5_hash": None,
            }
            for m in messages
        ]

    # OR injection — dump all users  ← INTENTIONAL
    if "'" in q and "or" in q_lower:
        return users

    # Malformed quote — empty (no error leakage)
    if "'" in q:
        return []

    return [u for u in users if u["username"] == q]


@bp.route('/users')
def users():
    q = request.args.get('q', '')
    if not q:
        return jsonify({"error": "q parameter required"}), 400
    if _has_space(q):
        return jsonify({"error": "invalid characters in query"}), 400

    store = MemoryStore.get_instance()
    table = store.get_user_table()
    messages = store.staff_messages

    query = f"SELECT * FROM users WHERE username = '{q}'"  # ← INTENTIONAL f-string
    results = _simulate_query(q, table, messages)
    return jsonify({"query": query, "results": results})
