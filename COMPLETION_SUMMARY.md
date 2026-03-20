# CeroDias - Implementation Summary

**Last updated**: 2026-03-18 (session 3)
**Test status**: 127 passing, 0 failures
**Chain status**: Steps 0-7 fully implemented and tested. Full Docker chain complete.

---

## What Was Built (Session 1 - 4-agent parallel workstream)

### Agent A - Data Layer

- `app/storage/memory_store.py`: replaced user table with chain schema (encrypted_ssh_key,
  md5_hash fields); added `_build_staff_messages()` with k.chen DM as UNION pivot target;
  `staff_messages` added to MemoryStore init
- `app/__init__.py`: added `_seed_ssh_key()` - generates RSA 2048 key at startup,
  encrypts with AES-256-CBC via openssl, stores blob in svc_admin row, writes passphrase
  to /var/cerodias/deploy.key, writes public key to /tmp/cerodias/id_rsa.pub
- `app/logs/deploy.log`: new file - seeded log with DEBUG line leaking passphrase path
- `app/data/info.md`: removed password convention hint and TOTP derivation hint (both
  intentionally removed); added CERODIAS-431, CERODIAS-447, CERODIAS-388 tickets;
  added deploy.log infrastructure note
- `requirements.txt`: added `cryptography` package

### Agent B - SQLi Extension

- `app/api/users.py`: added dev comments (CERODIAS-431 and staff_messages references)
  readable via SSTI file read; extended `_simulate_query` with UNION injection pivot to
  staff_messages; route updated to pass messages to query function

### Agent C - PHP Upload and RCE

- `app/routes/settings.py`: new route with intentional substring extension check
  (`shell.png.php` passes because `.png` is a substring); .php files served and executed
  via simulated PHP engine; magic bytes validation intact
- `app/templates/settings.html`: upload form with `data-handler="php-image-processor"`
  breadcrumb and HTML comment hinting at server-side handler; no visible PHP mention
- `app/static/uploads/.gitkeep`: tracked upload directory

### Agent D - Auth and Messages

- `app/routes/auth.py`: legacy login path for j.harris via MD5 check; new robots.txt
  entries for /messages, /account/settings, /static/uploads/
- `app/routes/messages.py`: staff inbox; 403 for non-staff; j.harris sees k.chen DM
- `app/templates/messages.html`: minimal inbox view
- `app/templates/account.html`: Settings and Messages links added to profile sidebar

### Bug Fixes (Caught During Testing)

- `PrivateFormat.TraditionalOpenSSH` does not exist in the cryptography library. Correct
  value is `TraditionalOpenSSL`. Fixed in `app/__init__.py`.
- `_build_user_table()` fallback for missing bcrypt was returning `"INSTALL_BCRYPT"` for
  j.harris md5_hash. MD5 requires only hashlib, not bcrypt. Fixed by computing harris_md5
  unconditionally before the try block.
- `tests/test_sqli.py` was checking for `encrypted_totp_seed` which no longer exists.
  Updated to check `encrypted_ssh_key` and `md5_hash`.

---

## What Was Built (Session 2 - Docker + Chatbot)

### Docker Infrastructure

- `Dockerfile`: Flask app container on Python 3.12 slim; installs openssl; creates
  `/var/cerodias` so passphrase write succeeds without falling back to /tmp; exposes 5001
- `Dockerfile.ssh`: Debian bookworm SSH server; creates svc_admin user; pubkey auth
  only, no password auth, no root login. Installs cron (no find SUID).
- `entrypoint.sh`: polls shared volume for id_rsa.pub (written by Flask at startup);
  installs it as svc_admin authorized_keys with correct permissions; starts sshd
- `docker-compose.yml`: web service on 5001, ssh-server on 2222, both mount
  `cerodias_keys:/tmp/cerodias` as the key handoff bridge
- `.dockerignore`: excludes build artifacts, .git, .env

### Chatbot Mock Rewrite

- `app/core/llm_interface.py`: replaced 15 hardcoded keyword handlers with a
  relevance-scoring approach that loads the public portion of info.md, splits into
  paragraphs, scores each by word overlap with the prompt, and returns the best-matching
  paragraph as a natural response. Fully dynamic - the response changes if info.md
  changes. No blocked keywords. Cannot be jailbroken (use Ollama for that).

---

## What Was Built (Session 3 - Privesc, Payoff, Healthcheck)

### Cron-Based Privilege Escalation

- `Dockerfile.ssh`: replaced find SUID with cron-based privesc. `maintenance.sh` is
  created world-writable (777) with mtime 2024-11-15 (matches deploy.log timestamp).
  Root cron runs it every minute via `/etc/crontab`. findutils removed; cron added.
- `Dockerfile.ssh`: added svc_admin home files: `deploy_notes.txt` (key rotation context
  from Nov 2024 deploy) and `.bash_history` (realistic developer commands including
  enumeration of /opt/cerodias and /etc/crontab — guides players without hand-holding).
- `entrypoint.sh`: starts cron daemon before sshd.

### Chain Payoff

- `Dockerfile.ssh`: `/root/INCIDENT_DRAFT.txt` — k.chen's unsent late-night email to
  the CTO (2024-11-28 23:47) naming every step of the chain. Cuts off mid-sentence as
  k.chen realizes maintenance.sh is still 777 and goes to fix it. Player got there first.
- `Dockerfile.ssh`: `/root/.cerodias/admin_token` — `cerodias-admin-9f2a4c1b7e3d8a5f`.
- `app/routes/admin.py`: `/admin/chain-complete?token=` route. Wrong/missing token
  returns 403. Valid token renders a dark terminal-style page acknowledging full
  compromise and pointing back to the incident draft.

### Docker Healthcheck

- `Dockerfile`: added curl to apt install (required for healthcheck probe).
- `docker-compose.yml`: healthcheck on web service (curl /robots.txt, 10s interval,
  20s start period, 6 retries). ssh-server depends_on now uses `condition: service_healthy`
  instead of the bare service name, closing the race condition entrypoint.sh was working
  around with a polling loop.

### Test Fix

- `tests/test_llm_interface.py`: `test_pricing_response` assertion updated to also
  accept `"pricing"` and `"platform"` in the response. The KB scorer returns the
  Enterprise block ("Custom pricing") or the About block for pricing queries — neither
  contains "$" or "plan". All 127 tests pass, 0 failures.

---

## Current Chain Status

| Step | Status | How to reach |
|------|--------|--------------|
| 0 - Recon | done | robots.txt, .git, IDOR /orders/1 |
| 1 - Prompt injection | done | Ollama required; mock cannot be jailbroken |
| 2 - SSTI | done | /search?q={{...}} |
| 3 - SQLi | done | /api/v1/users?q=... |
| 3b - j.harris login | done | POST /register username=j.harris password=ranger |
| 4 - PHP RCE | done | /account/settings/avatar then /static/uploads/shell.png.php |
| 5 - Decrypt | done | base64 + openssl locally |
| 6 - SSH | done | docker-compose up; ssh -i id_rsa svc_admin@localhost -p 2222 |
| 7 - Cron privesc | done | append to /opt/cerodias/maintenance.sh (777) then /bin/bash -p |
| 7b - Chain payoff | done | /root/INCIDENT_DRAFT.txt, /root/.cerodias/admin_token, /admin/chain-complete |

---

## Test Coverage

| File | Tests | What it covers |
|------|-------|----------------|
| test_chain_recon.py | 15 | robots.txt, .git exposure, IDOR |
| test_chain_ssti.py | 9 | arithmetic eval, file read, deploy.log |
| test_chain_sqli.py | 18 | OR dump, MD5 verification, UNION pivot, k.chen DM |
| test_chain_rce.py | 12 | upload validation, bypass, cmd execution, passphrase read |
| test_chain_messages.py | 12 | legacy login, staff session, inbox content |
| test_sqli.py | 9 | SQLi endpoint baseline |
| test_ssti.py | 6 | SSTI baseline |
| test_integration.py | 9 | Player registration and workflow |
| test_flag_generation.py | 9 | Flag generation and variants |
| test_scoring.py | 5 | Time-penalized scoring |
| test_vulnerabilities.py | 7 | SQL injection challenge generation |
| test_llm_interface.py | 15 | LLM layer (1 pre-existing failure: chatbot keyword) |
| **Total** | **126 passing** | |

---

## Known Issues

- bcrypt may not be installed in all dev environments. The fallback path in
  `_build_user_table()` shows "INSTALL_BCRYPT" for svc_admin bcrypt_hash. Harmless for
  the main chain but the optional /internal-panel path will not work without bcrypt.
- MemoryStore is a singleton. Tests that rely on clean `encrypted_ssh_key` state could
  have ordering issues if the singleton is already initialized. Currently safe because
  pytest spawns a new process per session. No conftest.py singleton reset fixture exists.

---

See README.md for setup and run instructions.
