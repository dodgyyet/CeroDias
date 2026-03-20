"""
/api/v1/users — internal user profile lookup

Not exposed in public API docs. Used by internal tooling and the admin portal.
Query by username via the q parameter.
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
    Run the user lookup query against the in-memory store.

    Simulates: SELECT * FROM users WHERE username = '<q>'
    Supports basic filter patterns used by internal tooling.
    """
    q_lower = q.lower()

    # UNION query — return rows from staff_messages table
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

    # OR condition — return all user rows
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

    query = f"SELECT * FROM users WHERE username = '{q}'"
    results = _simulate_query(q, table, messages)
    return jsonify({"query": query, "results": results})
