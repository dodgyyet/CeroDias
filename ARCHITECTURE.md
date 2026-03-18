# CeroDias Certmaster — Architecture

## What This Is

A simulated vulnerable company website. On the surface it sells IT certification
vouchers (CeroDias A-, Network-, Security-, etc.). Under the surface it is a
penetration testing education platform with an intentional Easter egg chain.

The three-tier access model mirrors real-world privilege escalation:

```
Tier 1 — Public           / , /register, /robots.txt, /.git/*, /search
Tier 2 — Registered user  /account, /orders/<id>, /purchase, /chat
Tier 3 — Admin            /dashboard, /leaderboard, /admin  (via /internal-panel)
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
│   │   ├── purchase.py             /purchase  (business logic flaw — debug crash)
│   │   ├── dashboard.py            /dashboard, /leaderboard  (Tier 3 — admin only)
│   │   ├── challenges.py           /challenge/<type>/<difficulty>
│   │   ├── submit.py               /submit  (flag submission)
│   │   ├── chatbot.py              /chat, /chat/history
│   │   ├── search.py               /search?q=  SSTI vulnerability
│   │   ├── settings.py             /account/settings  PHP upload bypass + RCE  [chain step 4]
│   │   ├── messages.py             /messages  staff inbox (j.harris parallel path)
│   │   └── admin.py                /admin, /admin/reset, /admin/stats
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
│   │   ├── llm_interface.py        Ollama local LLM (falls back to mock)
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
│   │                                orders (seeded), user_table, staff_messages
│   │
│   ├── data/
│   │   ├── info.md                 Public + internal sections. Full file in LLM system prompt.
│   │   │                           Internal section: chain hints, open tickets, infrastructure
│   │   └── logs/
│   │       └── deploy.log          Seeded log — DEBUG line leaks passphrase file path
│   │
│   ├── templates/                  Jinja2 HTML templates
│   │   ├── base.html               Navbar (tier-aware links), floating chatbot FAB, footer
│   │   ├── index.html              Public homepage — cert store, company facade
│   │   ├── login.html              Register page (Tier 1) — password field triggers legacy login
│   │   ├── account.html            Customer portal — order history, buy certs (Tier 2)
│   │   ├── settings.html           Profile picture upload (PHP bypass surface) [chain step 4]
│   │   ├── messages.html           Staff inbox — j.harris sees k.chen DM [parallel path]
│   │   ├── dashboard.html          CTF challenge dashboard (Tier 3 only)
│   │   ├── challenge.html          Individual challenge page (Tier 3)
│   │   ├── leaderboard.html        Global leaderboard (Tier 3)
│   │   ├── admin.html              Admin panel (Tier 3)
│   │   ├── error.html              Error page
│   │   ├── internal_panel.html     /internal-panel login form
│   │   └── internal_panel_home.html  Admin home after /internal-panel auth
│   │
│   └── static/
│       ├── css/style.css           CompTIA-inspired design system (full custom CSS)
│       ├── js/main.js              Floating chatbot FAB + send/history logic (innerHTML vuln)
│       └── uploads/                PHP webshells land here after upload bypass
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
    └── test_llm_interface.py       LLM layer (1 pre-existing chatbot failure)
```

---

## Three-Tier Access Model

### Tier 1 — Public (no session required)
Any visitor. Routes: `/`, `/register`, `/robots.txt`, `/.git/*`, `/search`.

`robots.txt` disallows: `/internal-panel`, `/api/v1/`, `/admin`, `/orders/`, `/.git`
(Standard recon target — tells players exactly where the interesting surfaces are.)

`/.git/*` serves fake but realistic git files:
- `HEAD` — branch pointer
- `config` — remote URL (internal GitHub)
- `COMMIT_EDITMSG` — reveals `/api/v1/users` endpoint by name
- `logs/HEAD` — commit history mentioning sequential order IDs and TOTP addition

### Tier 2 — Registered user (`session['player_id']` set)
Created via `/register`. Routes: `/account`, `/orders/<id>`, `/purchase`, `/chat`,
`/account/settings`, `/messages` (403 unless role=staff).

Staff sessions (`session['role'] == 'staff'`) are created by the legacy login path:
POST `/register` with `username=j.harris` and `password=ranger` triggers
`_check_legacy_login()` which validates against the MD5 hash and sets `role=staff`.

`/account` shows the player's cert purchase history. Order IDs are sequential integers
(visible in the table). IDOR: `/orders/<id>` has no ownership check — any logged-in
user can read any order. Order 1 belongs to `svc_admin`, leaking the admin username.

`/purchase` processes cert voucher purchases. Negative quantity causes an unhandled
`ValueError` inside `_generate_voucher()`. With `DEBUG=True`, Flask/Werkzeug renders
the interactive debugger page, leaking: full traceback, local variables (including
`all_orders` dict and `session` contents), internal file paths, and framework versions.

### Tier 3 — Admin (`session['internal_admin']` set)
Only reachable after completing the full exploit chain and POSTing valid credentials
to `/internal-panel`. Routes: `/dashboard`, `/leaderboard`, `/admin`.

`/dashboard` and `/leaderboard` are not linked anywhere. Normal users hitting them are
redirected to `/account`. Guests are redirected to `/register`.

---

## Intentional Vulnerabilities

| File | Vulnerability | Role in chain |
|------|--------------|---------------|
| `app/routes/search.py` | SSTI via `render_template_string` f-string | Step 2 — file read gateway |
| `app/routes/auth.py` | `.git/` exposure — fake commit history served | Recon — reveals /api/v1/users |
| `app/routes/orders.py` | IDOR — no ownership check on `/orders/<id>` | Recon — leaks svc_admin username |
| `app/routes/purchase.py` | Unhandled ValueError with DEBUG=True | Recon — Werkzeug debug page |
| `app/routes/settings.py` | PHP upload — substring ext check + .php execution | Step 4 — RCE to passphrase |
| `app/core/llm_interface.py` | Full info.md in system prompt, AI in restricted mode | Step 1 — jailbreak for roadmap |
| `app/data/info.md` | Internal section with chain hints | Revealed by prompt injection or SSTI |
| `app/data/logs/deploy.log` | DEBUG line leaks passphrase file path | Step 2 SSTI read target |
| `app/config.py` | Static SECRET_KEY, DEBUG=True | TOTP optional path + Werkzeug debugger |
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

SQLi on /api/v1/users?q=
    OR injection: svc_admin encrypted_ssh_key blob + j.harris MD5 hash
    UNION inject: staff_messages table, k.chen DM confirms blob + passphrase path

PHP upload bypass on /account/settings/avatar
    shell.png.php with PNG magic bytes passes substring extension check
    GET /static/uploads/shell.png.php?cmd=cat /var/cerodias/deploy.key

Decrypt:
    base64_decode(blob) | openssl enc -d -aes-256-cbc -pbkdf2 -k <passphrase>
    yields: svc_admin RSA private key

SSH: ssh -i id_rsa svc_admin@server   [Docker - future]
SUID privesc: root                     [Docker - future]
```

### Parallel path (j.harris route to same DM)

```
SQLi OR injection: j.harris md5_hash (MD5 of "ranger")
    hashcat -m 0 -a 0 hash.txt rockyou.txt
    yields: password "ranger" (instant)

POST /register: username=j.harris password=ranger
    _check_legacy_login() matches MD5 hash, sets session role=staff

GET /messages: j.harris inbox shows k.chen DM
    same information as UNION injection path
```

### Purchase flow

```
POST /purchase
    quantity >= 1: voucher issued, /orders/<id> created, redirect /account
    quantity < 1:  ValueError raised, Werkzeug debug page (DEBUG=True)
                   local vars visible: all_orders, session, price_per_unit, total
```

### Cert order IDOR

```
GET /orders/<int:order_id>    (requires Tier 2 login)
    no ownership check
    order 1: customer_username svc_admin (admin username leak)
    order 2: customer_username j.harris
    404 for unknown IDs
```

---

## Storage

`MemoryStore` is a singleton. All state lives in memory and resets on server restart.

```python
class MemoryStore:
    players:        {player_id: Player}
    challenges:     {challenge_id: Challenge}
    leaderboard:    [LeaderboardEntry]        # rebuilt on every read
    chatbot_history:{player_id: [ChatbotMessage]}
    user_table:     [dict]                    # svc_admin (bcrypt_hash, encrypted_ssh_key)
                                              # j.harris (md5_hash - CERODIAS-431)
    staff_messages: [dict]                    # k.chen DM - UNION injection target
    orders:         {order_id: dict}          # seeded at startup + player purchases
```

`user_table` and seeded orders are **not cleared on reset** — they represent the
"company data" that exists independently of the game state.

---

## Configuration

`app/config.py`:

```python
DIFFICULTY = 0          # 0=easy: static SECRET_KEY. 1+=runtime key (SSTI chain harder)
SECRET_KEY = 'flask-2b7f3a9c8d1e4f6a'    # INTENTIONALLY STATIC — do not change
DEBUG = True                              # INTENTIONALLY ON — Werkzeug debugger active
```

Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_MODEL` | `ollama` | `ollama` = local Ollama, `mock` = pattern matching |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral` | Model name |

---

## Design System (CSS)

Full custom CSS (`app/static/css/style.css`). No Bootstrap grid dependencies.
Google Fonts Inter loaded via `base.html`.

```
--navy:        #002B5C   primary
--orange:      #F26A21   accent / CTA
--blue-accent: #00A3E0   focus rings
--bg:          #F5F7FA   page background
--surface:     #FFFFFF   cards
--text:        #1A1A2E   body text
--muted:       #6B7280   secondary text
--border:      #E5E7EB   dividers
```

Chatbot: floating FAB button (`position: fixed; bottom: 28px; right: 28px`).
Click opens a 340×480 panel with spring-easing scale-in animation.

Navbar tier-awareness: `session.get('internal_admin')` controls whether
Challenges + Leaderboard links appear. All other nav is static.

---

## Running

```bash
pip install -r requirements.txt

# Without Ollama (prompt injection is mock):
python run.py

# With Ollama (real prompt injection):
ollama pull mistral
LLM_MODEL=ollama OLLAMA_MODEL=mistral python run.py

# Tests:
pytest tests/ -v    # 126 passing (1 pre-existing chatbot failure)
```

---

## Adding a New Vulnerability

1. Decide tier: `routes/` (page), `api/` (JSON), `internal/` (hidden)
2. Write the route — no comments labeling it vulnerable
3. Add intentional flaw: unsanitized input, no auth check, trust client data
4. Seed any required data in `memory_store.py`
5. Document in `HACKING.md` (what it requires, what it yields)
6. Update `robots.txt` if appropriate (disallowing invites enumeration)
7. Write a test confirming the vulnerability is present

See `VULNERABILITY_IDEAS.md` for planned next steps.
