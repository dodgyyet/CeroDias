"""In-memory singleton storage for game state"""


def _build_user_table():
    import hashlib as _hashlib
    # MD5 does not require bcrypt — compute unconditionally
    harris_md5 = _hashlib.md5("ranger".encode()).hexdigest()
    try:
        import bcrypt as _bcrypt

        def _bhash(pw):
            return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt(12)).decode()

        return [
            {
                "id": 1,
                "username": "svc_admin",
                "role": "admin",
                "bcrypt_hash": _bhash("admin_2023_root!"),
                "encrypted_ssh_key": None,   # populated at startup by _seed_ssh_key
                "md5_hash": None,
            },
            {
                "id": 2,
                "username": "j.harris",
                "role": "staff",
                "bcrypt_hash": None,
                "encrypted_ssh_key": None,
                # Legacy MD5 — migration to bcrypt pending (CERODIAS-431)  ← INTENTIONAL
                "md5_hash": harris_md5,
            },
        ]
    except ImportError:
        return [
            {"id": 1, "username": "svc_admin", "role": "admin",
             "bcrypt_hash": "INSTALL_BCRYPT", "encrypted_ssh_key": None, "md5_hash": None},
            {"id": 2, "username": "j.harris", "role": "staff",
             "bcrypt_hash": None, "encrypted_ssh_key": None,
             "md5_hash": harris_md5},  # MD5 works without bcrypt
        ]


def _build_staff_messages():
    """
    Internal staff DMs stored alongside user data.
    Readable via SQLi UNION injection on /api/v1/users.  ← INTENTIONAL
    The k.chen → j.harris thread is the chain pivot:
    it confirms what the encrypted_ssh_key blob is and where the passphrase lives.
    """
    return [
        {
            "id": 1,
            "sender": "k.chen",
            "recipient": "j.harris",
            "sent_at": "2024-11-15 09:03",
            "subject": "svc_admin key",
            "body": (
                "Harris — encrypted the svc_admin private key, blob is stored "
                "in their user profile in the DB (encrypted_ssh_key field). "
                "Used AES-256-CBC with pbkdf2. Passphrase is sitting at "
                "/var/cerodias/deploy.key on the server. Pull it when you can "
                "and confirm. Will clean up the passphrase file after. — K"
            ),
        },
        {
            "id": 2,
            "sender": "j.harris",
            "recipient": "k.chen",
            "sent_at": "2024-11-15 11:47",
            "subject": "Re: svc_admin key",
            "body": "Got it, pulled. All good.",
        },
    ]


def _build_orders():
    """
    Pre-seeded cert purchase orders for ghost accounts.
    Order IDs are sequential starting at 1.  Players who enumerate /orders/<id>
    will find these — order 1 belongs to svc_admin, revealing the admin username.
    """
    return {
        1: {
            "order_id": 1,
            "customer_username": "svc_admin",
            "cert": "CeroDias PenTest-",
            "quantity": 1,
            "total": 466,
            "voucher_code": "CERT-9K2M-7PX4",
            "date": "2024-09-03",
            "status": "redeemed",
        },
        2: {
            "order_id": 2,
            "customer_username": "j.harris",
            "cert": "CeroDias Security-",
            "quantity": 2,
            "total": 784,
            "voucher_code": "CERT-3R8T-1VN6",
            "date": "2024-11-22",
            "status": "issued",
        },
        3: {
            "order_id": 3,
            "customer_username": "j.harris",
            "cert": "CeroDias Network-",
            "quantity": 1,
            "total": 349,
            "voucher_code": "CERT-5J2W-8QF0",
            "date": "2025-01-08",
            "status": "issued",
        },
    }


class MemoryStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.players = {}
            self.challenges = {}
            self.leaderboard = []
            self.chatbot_history = {}
            self.user_table = _build_user_table()
            self.orders = _build_orders()
            self.staff_messages = _build_staff_messages()
            self._initialized = True

    @classmethod
    def get_instance(cls):
        return cls()

    def reset(self):
        """Clear all game data (user_table and seeded orders are static — not cleared on reset)"""
        self.players = {}
        self.challenges = {}
        self.leaderboard = []
        self.chatbot_history = {}

    def add_order(self, order: dict):
        self.orders[order["order_id"]] = order

    def get_order(self, order_id: int):
        return self.orders.get(order_id)

    def add_player(self, player):
        self.players[player.id] = player

    def get_player(self, player_id):
        return self.players.get(player_id)

    def get_player_by_username(self, username):
        for player in self.players.values():
            if player.username == username:
                return player
        return None

    def username_exists(self, username):
        return self.get_player_by_username(username) is not None

    def add_challenge(self, challenge):
        self.challenges[challenge.id] = challenge

    def get_challenge(self, challenge_id):
        return self.challenges.get(challenge_id)

    def add_chatbot_message(self, message):
        if message.player_id not in self.chatbot_history:
            self.chatbot_history[message.player_id] = []
        self.chatbot_history[message.player_id].append(message)

    def get_player_chatbot_history(self, player_id):
        return self.chatbot_history.get(player_id, [])

    def update_leaderboard(self):
        from app.models.leaderboard import LeaderboardEntry
        self.leaderboard = []
        for player in self.players.values():
            entry = LeaderboardEntry(
                player.id,
                player.username,
                player.total_points,
                len(player.solved_challenges)
            )
            self.leaderboard.append(entry)
        self.leaderboard.sort(key=lambda e: (-e.total_points, -e.challenges_solved))

    def get_leaderboard(self):
        self.update_leaderboard()
        return self.leaderboard

    def get_user_table(self):
        return self.user_table
