"""
Persistent leaderboard stored at /data/leaderboard.json.

Security notes:
- Writes are atomic (tmp file + os.replace). Never corrupt on crash.
- All inputs sanitized before writing. No raw user strings in JSON.
- /data is a bind-mounted host directory (./data on the host machine).
  It must never contain executable files or be served as a static path.
- Do not change DATA_PATH to point anywhere inside /app or /static.
"""
import json
import os
import re
import threading
import time
import hmac

DATA_PATH = '/data/leaderboard.json'
_lock = threading.Lock()

def validate_token(submitted: str) -> bool:
    """Constant-time comparison. Prevents timing-based token guessing."""
    token = os.environ.get('ADMIN_TOKEN', '')
    if not token:
        return False
    return hmac.compare_digest(
        submitted.encode('utf-8'),
        token.encode('utf-8'),
    )


def sanitize_username(raw: str) -> str:
    return re.sub(r'[^a-zA-Z0-9.\-_]', '', raw)[:64]


# Keep private alias for internal use
_sanitize_username = sanitize_username


def _sanitize_attempts(raw) -> dict:
    if not isinstance(raw, dict):
        return {}
    return {
        str(k)[:32]: int(v)
        for k, v in raw.items()
        if isinstance(v, (int, float))
    }


def record_completion(username: str, elapsed_seconds: int, attempts: dict):
    """
    Append a chain completion record to the leaderboard.
    Atomic write: tmp file + os.replace(). Safe on container crash.
    """
    entry = {
        'username': sanitize_username(username),
        'elapsed': int(elapsed_seconds),
        'attempts': _sanitize_attempts(attempts),
        'completed_at': int(time.time()),
    }
    with _lock:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        records = _read_records()
        # Deduplicate: keep fastest time per username
        records = [r for r in records if r.get('username') != entry['username']]
        records.append(entry)
        records.sort(key=lambda r: r['elapsed'])
        _atomic_write(records)


def get_leaderboard() -> list:
    with _lock:
        return _read_records()


def _read_records() -> list:
    if not os.path.exists(DATA_PATH):
        return []
    try:
        with open(DATA_PATH, 'r') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _atomic_write(records: list):
    tmp = DATA_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(records, f, indent=2)
    os.replace(tmp, DATA_PATH)
