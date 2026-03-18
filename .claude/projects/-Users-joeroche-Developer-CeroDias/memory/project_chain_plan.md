---
name: attack_chain_plan
description: Final attack chain design for CeroDias — SSTI→SQLi→RCE→SSH, no hash cracking on main path
type: project
---

The Easter egg chain was redesigned. Full spec in CHAIN_IMPLEMENTATION.md and story.md.

**Chain**: SSTI → SQLi (+ UNION pivot) → PHP upload/RCE → decrypt SSH key → SSH

**Why each step is required**:
- SSTI: discovers SQLi endpoint + passphrase file path from deploy.log
- SQLi: yields svc_admin encrypted_ssh_key blob + k.chen DM (UNION pivot to staff_messages)
- RCE: reads /var/cerodias/deploy.key (AES passphrase) from server filesystem
- Without all three, decryption is impossible

**Key data**:
- j.harris: MD5 hash of `ranger` (legacy, CERODIAS-431 migration backlog) — cracks instantly
- svc_admin: bcrypt/12, encrypted_ssh_key (AES-256-CBC pbkdf2, passphrase: cerodias-deploy-2024)
- staff_messages: k.chen→j.harris DM reachable via SQLi UNION injection
- Passphrase file: /var/cerodias/deploy.key (fallback: /tmp/cerodias/deploy.key)
- deploy.log at app/logs/deploy.log has DEBUG line leaking passphrase path

**Parallel path**: crack j.harris MD5 → login → /messages UI → same k.chen DM

**Optional hard mode**: /internal-panel still exists (bcrypt/12 + TOTP) but no hints remain in info.md

**Implementation split** (4 agents):
- Agent A: memory_store, __init__.py, deploy.log, info.md, requirements.txt (run first)
- Agent B: SQLi UNION extension in app/api/users.py (after A)
- Agent C: PHP upload/RCE in app/routes/settings.py + settings.html (after A)
- Agent D: auth legacy login, messages route/template, account.html, robots.txt (after A)

**Why:** Redesigned from old chain where hash cracking was too easy (password convention was handed out in info.md). New chain removed the convention hint and made SSTI+SQLi+RCE structurally co-dependent.
