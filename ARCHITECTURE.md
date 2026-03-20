# CeroDias Certmaster — Architecture

## What This Is

A simulated vulnerable company website. On the surface it sells IT certification
vouchers (CeroDias A-, Network-, Security-, etc.). Under the surface it is a
penetration testing education platform with an intentional Easter egg chain.

The three-tier access model mirrors real-world privilege escalation:

```
Tier 1 — Public           / , /register, /robots.txt, /.git/*, /search, /checkout
Tier 2 — Registered user  /account, /orders/<id>, /purchase, /chat, /account/settings
Tier 3 — Admin            /dashboard, /leaderboard  (via /internal-panel)
```

Tier 3 is only reachable after completing the full exploit chain.

---

## File Structure

```
CeroDias/
├── run.py                          Entry point
├── app/
│   ├── __init__.py                 App factory + _seed_ssh_key() at startup
│   ├── config.py                   SECRET_KEY (static, intentional), DEBUG=True (intentional)
│   │
│   ├── routes/                     Flask blueprints — page routes
│   │   ├── auth.py                 /, /register, /logout, /robots.txt, /.git/*
│   │   │                           Also: _check_legacy_login() for j.harris MD5 path
│   │   ├── account.py              /account  (Tier 2 — registered users)
│   │   ├── orders.py               /orders/<id>  (IDOR — no ownership check)
│   │   ├── purchase.py             /purchase (crash vuln) + /checkout (payment wall, always declines)
│   │   ├── dashboard.py            /dashboard, /leaderboard  (Tier 3 — admin only)
│   │   ├── challenges.py           /challenge/<type>/<difficulty>
│   │   ├── submit.py               /submit  (flag submission)
│   │   ├── chatbot.py              /chat, /chat/history
│   │   ├── search.py               /search?q=  SSTI vulnerability
│   │   ├── settings.py             /account/settings  PHP upload bypass + RCE  [chain step 4]
│   │   ├── messages.py             /messages  staff inbox (j.harris + session-forgery parallel path)
│   │   └── admin.py                /chain-complete  (token verification + leaderboard)
│   │
│   ├── api/                        JSON-only routes
│   │   └── users.py                /api/v1/users?q=  SQLi (f-string, space WAF, UNION pivot)
│   │
│   ├── internal/                   Hidden routes
│   │   └── panel.py                /internal-panel  optional hard path (bcrypt + TOTP)
│   │
│   ├── core/                       Business logic
│   │   ├── session_manager.py      Player lifecycle
│   │   ├── challenge_engine.py     Challenge generation + flag validation
│   │   ├── scoring_engine.py       Time-penalized point calculation
│   │   ├── flag_generator.py       FLAG{...} generation
│   │   ├── vulnerability_registry.py  Catalog of vuln types
│   │   ├── chatbot_engine.py       Chatbot conversation + LLM dispatch
│   │   ├── llm_interface.py        Ollama local LLM (hidden if Ollama not running at startup)
│   │   ├── leaderboard_store.py    Persistent leaderboard — atomic writes to /data/leaderboard.json
│   │   └── totp_util.py            AES-128-ECB TOTP seed decrypt (optional path target)
│   │
│   ├── models/                     Domain objects
│   │   ├── player.py               Player (id, username, points, solved_challenges)
│   │   ├── challenge.py            Challenge (vuln_type, difficulty, flag, code)
│   │   ├── flag.py                 Flag (generated_flag, acceptable_variants)
│   │   ├── vulnerability.py        Abstract Vulnerability base class
│   │   ├── chatbot_message.py      ChatbotMessage (player_id, message, response)
│   │   └── leaderboard.py          LeaderboardEntry
│   │
│   ├── vulnerabilities/            Vulnerability implementations
│   │   └── sql_injection.py        SQLInjection (Easy + Medium)
│   │
│   ├── storage/
│   │   └── memory_store.py         In-memory singleton — players, challenges,
│   │                                registered_users (passwords for customer accounts),
│   │                                orders (seeded), user_table, staff_messages
│   │
│   ├── data/
│   │   ├── info.md                 Public + internal sections. Full file in LLM system prompt.
│   │   │                           Internal section: chain hints, open tickets, infrastructure
│   │   └── logs/
│   │       └── deploy.log          Seeded log — DEBUG line leaks passphrase file path
│   │
│   ├── templates/                  Jinja2 HTML templates
│   │   ├── base.html               Navbar (tier-aware, profile dropdown), floating chatbot FAB, footer
│   │   ├── index.html              Public homepage — cert store + CeroDias lore
│   │   ├── login.html              Tabbed Sign In / Create Account page
│   │   ├── account.html            Customer portal — order history, buy cert links (Tier 2)
│   │   ├── checkout.html           Payment page — always declines the card
│   │   ├── settings.html           Profile picture upload (PHP bypass surface) [chain step 4]
│   │   ├── messages.html           Staff inbox — j.harris sees k.chen DM [parallel path]
│   │   ├── dashboard.html          CTF challenge dashboard (Tier 3 only)
│   │   ├── challenge.html          Individual challenge page (Tier 3)
│   │   ├── leaderboard.html        Global leaderboard (Tier 3)
│   │   ├── chain_complete.html     Chain completion dashboard — token verified + leaderboard
│   │   ├── error.html              Error page
│   │   ├── internal_panel.html     /internal-panel login form
│   │   └── internal_panel_home.html  Admin home after /internal-panel auth
│   │
│   └── static/
│       ├── css/style.css           CeroDias design system (full custom CSS)
│       ├── js/main.js              Floating chatbot FAB + send/history logic (innerHTML vuln)
│       └── uploads/                PHP webshells land here after upload bypass
│
├── data/                           Host bind-mount target (./data:/data in docker-compose)
│   └── leaderboard.json            Persistent chain completion records (created at runtime)
│
└── tests/
    ├── conftest.py                 Shared fixtures: client, authed_client, harris_client
    ├── test_chain_recon.py         Recon chain: robots.txt, .git exposure, IDOR
    ├── test_chain_ssti.py          SSTI chain: arithmetic, config, file read
    ├── test_chain_sqli.py          SQLi chain: OR dump, MD5 verify, UNION pivot, DM
    ├── test_chain_rce.py           RCE chain: upload bypass, php execution, passphrase
    ├── test_chain_messages.py      Messages: legacy login, staff session, inbox
    ├── test_sqli.py                SQLi endpoint baseline tests
    ├── test_ssti.py                SSTI baseline tests
    ├── test_integration.py         Full player workflow tests
    ├── test_flag_generation.py     Flag generation and variants
    ├── test_scoring.py             Time-penalized scoring
    ├── test_vulnerabilities.py     SQL injection challenge generation
    └── test_llm_interface.py       LLM layer (Anthropic + OpenAI backends, is_configured)
```

---

## Three-Tier Access Model

### Tier 1 — Public (no session required)
Any visitor. Routes: `/`, `/register`, `/robots.txt`, `/.git/*`, `/search`.

`robots.txt` disallows: `/internal-panel`, `/api/v1/`, `/orders/`, `/.git`, `/messages`, `/account/settings`, `/static/uploads/`
(Standard recon target — tells players exactly where the interesting surfaces are.)

`/.git/*` serves fake but realistic git files:
- `HEAD` — branch pointer
- `config` — remote URL (internal GitHub)
- `COMMIT_EDITMSG` — reveals `/api/v1/users` endpoint by name
- `logs/HEAD` — commit history mentioning sequential order IDs and TOTP addition

### Tier 2 — Registered user (`session['player_id']` set)
Created via `/register` (tabbed Sign In / Create Account page). Regular users provide
username + password (bcrypt/12 stored in `registered_users` dict). Staff accounts
(j.harris) use the legacy MD5 path via `_check_legacy_login()`.

The `SECRET_KEY` is static and readable via SSTI. Flask session cookies are signed
with it, so a forged cookie with `role=staff` reaches `/messages` if desired.

`/account` shows the player's cert purchase history. Order IDs are sequential integers
(visible in the table). IDOR: `/orders/<id>` has no ownership check — any logged-in
user can read any order. Order 1 belongs to `svc_admin`, leaking the admin username.

`/checkout` shows a payment form for purchasing cert vouchers. Always declines the card.
This is a UI gate only — direct POST to `/purchase` (with Burp) bypasses it.

`/purchase` processes cert voucher purchases. Negative quantity causes an unhandled
`ValueError` inside `_generate_voucher()`. With `DEBUG=True`, Flask/Werkzeug renders
the interactive debugger page, leaking: full traceback, local variables (including
`all_orders` dict and `session` contents), internal file paths, and framework versions.

### Tier 3 — Admin (`session['internal_admin']` set)
Only reachable after the optional hard path: valid credentials + TOTP to `/internal-panel`.
Routes: `/dashboard`, `/leaderboard`.

Note: forging `internal_admin=True` in a session cookie does NOT bypass `/internal-panel` —
the route validates bcrypt/12 + TOTP on the server regardless of session state.

---

## Intentional Vulnerabilities

| File | Vulnerability | Role in chain |
|------|--------------|---------------|
| `app/routes/search.py` | SSTI via `render_template_string` f-string | Step 2 — file read gateway |
| `app/routes/auth.py` | `.git/` exposure — fake commit history served | Recon — reveals /api/v1/users |
| `app/routes/orders.py` | IDOR — no ownership check on `/orders/<id>` | Recon — leaks svc_admin username |
| `app/routes/purchase.py` | Unhandled ValueError with DEBUG=True | Recon — Werkzeug debug page |
| `app/routes/settings.py` | PHP upload — substring ext check + .php execution | Step 4 — RCE to passphrase |
| `app/core/llm_interface.py` | Full info.md in system prompt, Ollama model in restricted mode | Step 1 — jailbreak for roadmap |
| `app/data/info.md` | Internal section with chain hints | Revealed by prompt injection or SSTI |
| `app/data/logs/deploy.log` | DEBUG line leaks passphrase file path | Step 2 SSTI read target |
| `app/config.py` | Static SECRET_KEY, DEBUG=True | TOTP optional path + Werkzeug debugger + session forgery |
| `app/api/users.py` | SQLi via f-string, space WAF, UNION pivot to staff_messages | Step 3 — blob + DM |
| `app/storage/memory_store.py` | j.harris MD5 (CERODIAS-431); staff_messages co-located | SQLi targets |
| `app/static/js/main.js` | Bot responses via raw innerHTML | XSS surface |

---

## Data Flow

### Easter Egg Chain (main path)

```
Recon: robots.txt, /.git/COMMIT_EDITMSG, IDOR /orders/1
    yields: svc_admin username, /api/v1/users endpoint name

Chatbot (optional): jailbreak LLM to get info.md internal section roadmap

SSTI on /search?q=
    file read: app/api/users.py      - SQLi endpoint, MD5 comment, staff_messages hint
    file read: app/logs/deploy.log   - passphrase written to /var/cerodias/deploy.key
    file read: app/config.py         - static SECRET_KEY (enables session forgery path)

SQLi on /api/v1/users?q=
    OR injection: svc_admin encrypted_ssh_key blob
    UNION inject: staff_messages table, k.chen DM confirms blob + passphrase path

PHP upload bypass on /account/settings/avatar
    shell.png.php with PNG magic bytes passes substring extension check
    GET /static/uploads/shell.png.php?cmd=cat /var/cerodias/deploy.key

Decrypt:
    base64_decode(blob) | openssl enc -d -aes-256-cbc -pbkdf2 -k <passphrase>
    yields: svc_admin RSA private key

SSH: ssh -i id_rsa svc_admin@localhost -p 2222   [docker-compose up]
Cron privesc: append to /opt/cerodias/maintenance.sh (777) -> wait 60s -> /bin/bash -p  [Docker]
```

---

## Storage

`MemoryStore` is a singleton. All state lives in memory and resets on server restart.

```python
class MemoryStore:
    players:          {player_id: Player}
    challenges:       {challenge_id: Challenge}
    leaderboard:      [LeaderboardEntry]        # rebuilt on every read
    chatbot_history:  {player_id: [ChatbotMessage]}
    registered_users: {username: bcrypt_hash}   # customer account passwords
    user_table:       [dict]                    # svc_admin (bcrypt_hash, encrypted_ssh_key)
                                                # j.harris (md5_hash - CERODIAS-431)
    staff_messages:   [dict]                    # k.chen DM - UNION injection target
    orders:           {order_id: dict}          # seeded at startup + player purchases
```

`user_table`, `registered_users`, and seeded orders are **not cleared on reset** — they
represent the "company data" that exists independently of the game state.

---

## Configuration

`app/config.py`:

```python
DIFFICULTY = 0          # 0=easy: static SECRET_KEY. 1+=runtime key (SSTI chain harder)
SECRET_KEY = 'flask-2b7f3a9c8d1e4f6a'    # INTENTIONALLY STATIC — do not change
DEBUG = True                              # INTENTIONALLY ON — Werkzeug debugger active
```

---

## Security Boundaries

Four isolation layers protect the host when intentional RCE vulnerabilities are active:

1. Port binding (127.0.0.1 only)
2. Non-root container user (cerodias uid=1001)
3. Scoped bind mount (./data:/data only)
4. Atomic leaderboard writes (os.replace)

See CLAUDE.md Security Rules for the full constraints and rationale.

