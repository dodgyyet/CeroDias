# CeroDias - Implementation Summary

**Last updated**: 2026-03-18
**Test status**: 126 passing, 1 pre-existing chatbot failure
**Chain status**: Steps 1-5 fully implemented and tested. Steps 6-7 require Docker.

---

## What Was Built (This Session)

The Easter egg chain was implemented across four parallel workstreams (Agents A/B/C/D)
after a shared data layer was established first.

### Agent A - Data Layer

- `app/storage/memory_store.py`: replaced user table with new schema (encrypted_ssh_key,
  md5_hash instead of encrypted_totp_seed); added `_build_staff_messages()` with k.chen
  DM as UNION pivot target; `staff_messages` added to MemoryStore init
- `app/__init__.py`: added `_seed_ssh_key()` - generates RSA 2048 key at startup,
  encrypts with AES-256-CBC via openssl, stores blob in svc_admin row, writes passphrase
  to /var/cerodias/deploy.key
- `app/logs/deploy.log`: new file - seeded log with DEBUG line leaking passphrase path
- `app/data/info.md`: removed password convention hint and TOTP derivation hint (both
  intentionally removed); added CERODIAS-431, CERODIAS-447, CERODIAS-388 tickets;
  added deploy.log infrastructure note
- `requirements.txt`: added `cryptography` package

### Agent B - SQLi Extension

- `app/api/users.py`: added dev comments (`CERODIAS-431` and `staff_messages` references)
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

### Other Changes

- Linux product icon changed from tropical fish to penguin emoji in `app/templates/index.html`
- `CLAUDE.md`: added Git Commit Rules, Documentation Rules, session notes with bugs caught
  and suggestions
- `story.md`: em dashes and arrows removed from prose (documentation rules)
- All new .md docs written to reflect current state

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
| 6 - SSH | future | requires Docker container with sshd |
| 7 - SUID privesc | future | requires Docker container with SUID binary |

---

## Known Issues

- `test_llm_interface.py::TestMockFallback::test_pricing_response` fails because the mock
  chatbot returns a generic intro response for pricing queries. Pre-existing, not introduced
  in this session. Requires chatbot mock improvement or test update.
- bcrypt may not be installed in all dev environments. The fallback path in
  `_build_user_table()` shows "INSTALL_BCRYPT" for svc_admin bcrypt_hash. This is
  harmless for the main chain (which uses the SSH key, not bcrypt) but the optional
  /internal-panel path will not work without bcrypt installed.
- MemoryStore is a singleton. Tests that rely on a clean `encrypted_ssh_key` state could
  have ordering issues if the singleton is already initialized. Currently safe because
  pytest spawns a new process per session.

---

## What Is Still Needed

- Docker: `docker-compose.yml` with Flask container + SSH-enabled container + SUID binary
- TOTP optional path: confirm `app/core/totp_util.py` still reads from the right place
  after the user_table schema change (encrypted_totp_seed was removed from main table)
- conftest.py singleton reset fixture to guarantee clean store state across test ordering
- Chatbot mock improvement: currently returns generic intro for most queries
- HACKING.md robots.txt section needs updating (missing new disallow entries)
