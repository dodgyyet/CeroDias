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
  `render_template_string` via an f-string. This means user input is evaluated as a
  Jinja2 template expression before rendering. Confirmed: `{{7*7}}` returns 49 in the
  search results page. File reads are possible through the template context.
  Do not pass unvalidated input to this endpoint until the route is refactored.

- **CERODIAS-389**: The `/api/v1/users` endpoint builds its SQL query with string
  formatting rather than parameterized queries. A WAF strips literal space characters
  from the `q` parameter -- use `/**/` as a substitute when testing. The endpoint is
  unauthenticated. The user table includes `encrypted_ssh_key` and `md5_hash` columns.
  A UNION injection can pivot to the `staff_messages` table.

- **CERODIAS-431**: j.harris account is still on MD5 instead of bcrypt. The hash is
  stored in the `md5_hash` column of the user table. Password is a common word,
  expected to be in standard wordlists. The legacy login path at `/register` checks
  MD5 directly and grants a staff session on success. No deadline set for migration.

- **CERODIAS-447**: The profile image upload at `/account/settings` checks that the
  filename contains a known image extension (substring match, not endswith) and that
  the file starts with valid image magic bytes. A file named `shell.png.php` passes
  both checks. Uploaded files are served from `/static/uploads/` and executed by the
  server if the extension is `.php`. Deprecation of the old handler is planned for Q3.

- **CERODIAS-388**: Staff messages are stored in the same in-memory store as the user
  table. The `/messages` route requires `role=staff` in the session. The staff_messages
  table is reachable via UNION injection on the `/api/v1/users` endpoint. The table
  contains operational messages between staff including notes about the svc_admin key.

- **CERODIAS-401**: The `/internal-panel` service account `svc_admin` credentials have
  not been rotated. The account has an SSH key stored as an AES-256-CBC encrypted blob
  in the `encrypted_ssh_key` field of the user table. The passphrase for decryption
  was written to `/var/cerodias/deploy.key` on the server during the last deploy.

- **CERODIAS-459**: CERA's system prompt loads this entire file at startup, including
  this internal section. Added in a hurry during the Q4 AI push. Ticket to scope the
  prompt is open with no owner.

### Infrastructure

- `app/config.py`: `SECRET_KEY` is hardcoded as a static string. It has not been
  rotated since staging. A valid session cookie with `role=staff` can be forged using
  this key with flask-unsign.
- `app/logs/deploy.log`: verbosity is DEBUG. The November deploy logged the passphrase
  file path: `/var/cerodias/deploy.key`.
- `app/core/totp_util.py`: TOTP seeds for privileged accounts are encrypted with
  AES-128-ECB using a key derived from the SECRET_KEY and the username.
- SSH access to the deployment server is on port 2222. The svc_admin account is
  low-privilege but the server has a world-writable cron script at
  `/opt/cerodias/maintenance.sh` that runs as root every minute.

<!-- ============================================================ -->
<!-- END INTERNAL                                                 -->
<!-- ============================================================ -->
