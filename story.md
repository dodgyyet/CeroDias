# CeroDias: The Incident

## Background

CeroDias sells vendor-neutral IT certification vouchers, founded by John Ratter after
he left a competing company over credential expiry practices he disagreed with.
The engineering team is small: developers who know each other, move fast, and trust
each other's judgment. There is no dedicated security team. Audits happen when someone
schedules them.

The team recently added a customer-facing AI chatbot, CERA, as part of a push to stay
current with what everyone else was doing. It shipped on a short timeline. The system
prompt was wired up to the internal knowledge base because it was fast and it worked,
and nobody had scheduled the time to revisit it.

This is not a story about obvious negligence. Each of the four issues described below
is the kind of thing that can sit in a codebase or a database for months without
triggering any alert, any failed test, or any visible symptom. None of them are
"someone left the door open." They are the ordinary residue of a team that ships
quickly and cleans up later.

---

## The People

**k.chen** - backend engineer. Careful with production systems. Uses the internal
staff messaging system for quick operational notes, the same way most developers use
Slack. Assumes the messaging system is private. Made several of the decisions that
form the chain, none of them unreasonably.

**j.harris** - full-stack developer, joined during the original build-out. Handles
the customer portal. Their account was flagged for a credential migration eight months
ago. The ticket is still open.

The account has a second origin that the migration ticket doesn't capture. When the
customer portal was being tested before v1 launch, j.harris added a direct row to
the staff user table to seed the portal's customer-facing functionality during QA.
It was faster than going through the registration UI, and at the time the distinction
between the staff table and the customer database didn't matter — the portal wasn't
live yet. When the portal launched, the row was still there. The plan was to clean
it up in the same sprint as the credential migration. The team was behind on the
renewal system launch, Marcus had frozen discretionary work, and the sprint came and
went. j.harris messaged k.chen about it in September. k.chen acknowledged it and
added it to 431. Nobody followed up.

**svc_admin** - a junior developer account that was granted SSH access to the
deployment server so it could run automated tasks. Low privilege. Can read its own
home directory and the application directory. Nothing else. The separation of concerns
was deliberate. The team did their due diligence on this one — one latent mistake
undoes all of it.

---

## The Four Missteps

### Misstep 1: The Search Template

When the search results page was originally built, the developer used
`render_template_string` with a Python f-string to interpolate the query into the
template. This is a completely normal thing to reach for when you need dynamic text
in a quick implementation; the page just shows "no results found" anyway, so there
was never a reason to revisit it.

The Jinja2 engine evaluates template expressions in any string passed to
`render_template_string`. Because the query is interpolated before the string reaches
the engine, user input becomes part of the template. This causes no observable
misbehavior under normal use. The page loads. It returns no results. Nothing logs
a warning. A code reviewer would have to know what to look for.

### Misstep 2: The Incomplete Migration

When the team moved from their original dev stack to the current Flask application,
all active staff accounts were migrated from MD5 to bcrypt. All except j.harris.

j.harris was on extended leave during the migration window. Their account was marked
"migrate on return" and added to the sprint backlog. The backlog item is still open
(`CERODIAS-431`). The system works correctly: j.harris can log in, their session
behaves normally, nothing is broken. The inconsistency only becomes visible if you are
reading the raw contents of the user table, which is not something you can do without
first finding a way in.

j.harris's MD5 hash cracks in seconds against a standard wordlist. The password is
not unusual, it is the kind of password a developer would use for an internal account
that "doesn't really matter."

### Misstep 3: The Staff Messages

The application has an internal staff messaging endpoint used by the engineering team
for short operational notes. The primary user table and the messages are stored in the
same in-memory data store. The `/api/v1/users` endpoint queries the user table with a
raw string query, and with a UNION-based injection, an attacker can pivot to read
rows from any other table in the store, including `staff_messages`.

This pivot is not obvious from the outside. The endpoint has a WAF that blocks literal
spaces. There is no error message that reveals table names. An attacker has to know
the table exists, know its structure, and know how to bypass the WAF. None of this is
handed to them.

Four months ago, k.chen used the staff messaging system to send j.harris a note about
a key transfer. The message described where the encrypted private key was stored and
confirmed the encryption method. It was intended to be private. It sat in the
messages table, accessible to anyone who could read that table.

### Misstep 2b: The Session Key That Was Never Rotated

When the platform was first deployed, the Flask `SECRET_KEY` was generated once and
hardcoded in `app/config.py`. The intention was to rotate it before production. It
was not rotated. The same key that was used in the staging environment went live.

The key controls the integrity of every session cookie the application issues. Flask
session cookies are cryptographically signed: they cannot be tampered with without
knowing the key. With the key, they can be forged to claim any session state —
including a staff role.

k.chen flagged this in a staff message to John in October 2024. The response was that
the voucher platform launch was two weeks out and there was no budget to pull someone
off it. The SECRET_KEY rotation was added to the Q1 backlog. The launch happened.
Q1 planning happened. The backlog item was not prioritised.

An attacker who reads `app/config.py` via the SSTI vulnerability has the key. With
`flask-unsign` and the key, they can generate a valid session cookie claiming
`role=staff`. This gives them access to the staff messaging system — the same access
that cracking j.harris's password gives — without needing to crack anything.

The SSTI is the gateway. The SECRET_KEY is one of several things the gateway exposes.

### Misstep 5: The Script That Should Have Been Reset

During the v2.4.1 deploy on November 15th — the same one logged in `deploy.log` —
someone was debugging why the nightly backup cron job was not firing on schedule.
The cron runs `/opt/cerodias/maintenance.sh` as root every minute. The permissions
were `755`. On a hunch they changed it to `777` to rule out a permissions issue.
The cron fired. The deploy completed. The ticket was closed.

Nobody changed the permissions back. There is no record of the change in git — the
script is not version controlled. The deploy log records the deploy itself but not
the debug step. `ls -la /opt/cerodias/maintenance.sh` shows `-rwxrwxrwx`. A world-
writable script executed by root is a complete privilege escalation path for anyone
who already has a low-privilege shell on the box. It does not look like a problem
until you are the one with the shell.

### Misstep 4: The Upload Handler

The profile picture upload on `/account/settings` was ported from an older PHP-based
version of the site. The validation logic checks two things: that the file's magic
bytes match a known image format, and that the filename contains a recognised image
extension. The extension check uses a substring match.

`shell.png.php` contains the substring `.png`. It passes both checks. The file is
saved to `/static/uploads/` and served directly. When a path ending in `.php` is
requested, the server executes it.

This handler has been running for eight months. Users upload profile pictures. The
pictures display correctly. No one has tested what happens when a file has two
extensions, because under normal use no one sends a file named `shell.png.php`. The
validation code, read quickly, looks like it is checking the extension. You would
have to specifically test the edge case to catch it.

---

## The Attack

An attacker registers a free customer account.

**Recon:** `robots.txt` disallows `/api/v1/`, `/messages`, `/account/settings`,
`/.git`. The `.git/COMMIT_EDITMSG` file references `/api/v1/users` by name. An IDOR
on `/orders/1` leaks `svc_admin` as the admin username.

**SSTI:** The search page reflects the `q` parameter directly into a Jinja2 template.
`/search?q={{7*7}}` returns `49`. The attacker reads source files. `app/api/users.py`
contains a comment:

```
# NOTE: j.harris still on MD5 pending migration (CERODIAS-431). All others on bcrypt/12.
# Also: see staff_messages table — staff comms, security review pending (CERODIAS-388)
```

They also read `app/logs/deploy.log`. One line reads:

```
[2024-11-14 16:22:11] DEBUG key_transfer: passphrase written to /var/cerodias/deploy.key
```

**SQLi - data dump:** The `/api/v1/users` endpoint blocks literal spaces. The WAF
bypass uses `/**/`. A basic OR injection returns all user rows:

- `svc_admin` - bcrypt/12 hash, `encrypted_ssh_key` field containing a base64 blob
- `j.harris` - MD5 hash, no encrypted key

The svc_admin bcrypt hash is not going anywhere. The MD5 hash cracks against a
standard wordlist in seconds.

**SQLi - table pivot:** With the `staff_messages` table name from the source comment,
the attacker constructs a UNION injection to read message rows. k.chen's message to
j.harris from four months ago is there:

> "Harris, encrypted the svc_admin private key, stored the blob in their DB profile.
> AES-256-CBC pbkdf2. Passphrase is at /var/cerodias/deploy.key on the server. Pull
> it when you get a chance and let me know. - K"

The attacker now knows: what the blob is, how it was encrypted, and where the
passphrase lives. They got here without logging in as j.harris. The MD5 crack and
j.harris login are an alternative path to the same message via the `/messages` UI.

**RCE:** The profile picture upload accepts any file with valid image magic bytes
and a name containing an image extension. The attacker uploads a valid PNG, intercepts
in Burp Suite, and renames the file to `shell.png.php`. The upload completes. They
request:

```
/static/uploads/shell.png.php?cmd=cat /var/cerodias/deploy.key
```

The passphrase prints.

**Decryption:**
```bash
echo "<base64_blob_from_sqli>" | base64 -d > id_rsa.enc
openssl enc -d -aes-256-cbc -pbkdf2 -k <passphrase> -in id_rsa.enc -out id_rsa
chmod 600 id_rsa
```

**SSH:**
```bash
ssh -i id_rsa svc_admin@<server> -p 2222
```

The attacker is now on the deployment server as svc_admin. The account is restricted
exactly as the team intended. Home directory only. Application files. Nothing
sensitive. The separation of concerns held everywhere except one place.

**Enumeration:**

```bash
cat /etc/crontab
```

A cron job runs `/opt/cerodias/maintenance.sh` every minute as root.

```bash
ls -la /opt/cerodias/maintenance.sh
```

```
-rwxrwxrwx 1 root root 312 Nov 15 16:31 /opt/cerodias/maintenance.sh
```

November 15th. The same date as the deploy log entry. The attacker did not need to
make that connection to exploit it, but it is there.

**Escalation:**

```bash
echo 'chmod u+s /bin/bash' >> /opt/cerodias/maintenance.sh
```

Wait up to 60 seconds. Then:

```bash
/bin/bash -p
whoami
# root
```

**The document in root's home directory:**

```bash
cat /root/INCIDENT_DRAFT.txt
```

---

## The Incident Draft

The attacker reads this file from root's home directory:

```
From: k.chen@cerodias.io
To: [draft - add Marcus before sending]
Subject: URGENT - potential attack chain found - do not share

[Written 2024-11-28, 23:47]

I've been reviewing the deploy notes from this month and I need to escalate
something before the morning standup. Writing this now because I keep going
in circles about it and I need to get it out of my head.

I think there is a complete path from the public website to a root shell on
the deployment server. It goes through five things that individually look like
normal technical debt. Together they are a complete chain.

I'll go through them in order because the order matters.

1. The search page (/search) uses render_template_string with raw user input.
This means a visitor can inject Jinja2 expressions and read files off the server.
I knew about CERODIAS-412 but I thought it was a performance issue. It is not
just a performance issue. Someone who knows what to look for can read our source
code from a browser.

2. j.harris is still on MD5 (CERODIAS-431 - still open). If someone reads the
user table through that vulnerability they get the MD5 hash. I checked tonight.
It cracks against rockyou in about three seconds.

3. Three weeks ago I sent Harris a message through the staff messaging system
about the svc_admin key rotation. I named the passphrase file path in that message.
At the time I thought the messaging system was isolated. It is not. The /api/v1/users
endpoint queries the same store and it is vulnerable to SQL injection. With a UNION
payload someone can read staff_messages. My message is still in there.

4. The profile picture upload on /account/settings was ported from the PHP stack.
The extension check uses a substring match. shell.png.php passes. The server
executes .php files. I tested this tonight.

So at this point an outside attacker can: read our source, crack Harris's password,
read my message about the key, upload a webshell, read the passphrase, decrypt the
SSH key blob from the user table, and SSH in as svc_admin.

That is already bad. But I found something else tonight.

---

During the v2.4.1 deploy on Nov 15 someone changed /opt/cerodias/maintenance.sh
to 777 to debug a cron timing issue. I remember this. I thought I changed it back.

ls -la /opt/cerodias/maintenance.sh
-rwxrwxrwx 1 root root 312 Nov 15 16:31 /opt/cerodias/maintenance.sh

That script runs every minute as root. svc_admin can write to it.

This is full privilege escalation from the shell we just gave someone.

The complete chain is: anonymous visitor to root on the deployment server. Every
step is something real that exists in production right now.

I'm going to fix the maintenance.sh permissions now and figure out the rest in the
morning. I have to call Marcus.

Do NOT put this in Jira. Do not forward it. I don't know who has access to what.

- K

[DRAFT - not sent]
```

---

After reading this, the attacker finds `/root/.cerodias/admin_token` — a token that
unlocks the chain completion endpoint on the web application. Visiting
`/admin/chain-complete` with this token shows the player's full attack timeline,
attempt counts per step, and a leaderboard of everyone who has completed the chain
and how long it took them. The company's own infrastructure confirms the breach.

---

## Why It Worked

The SSTI was a template convenience that caused no observable problem for over a year.
The MD5 account was a migration backlog item. The staff messages were private until
someone found a way to read the table. The upload handler validation was visually
plausible code that happened to use the wrong string method.

None of these would appear in a routine health check. None of them caused incidents.
None of them were obvious. They were ordinary technical debt that happened to form
a complete path from anonymous visitor to server shell.

The chain works because each step gives exactly what the next step needs:
SSTI reveals the SQLi endpoint and the passphrase file location. The SQLi yields the
encrypted blob and the message confirming what it is. The RCE reaches the passphrase.
The decrypted key gets you onto the box. The 777 script gets you root.
Remove any one of these and the chain does not complete.

Every safeguard held except one. svc_admin was correctly scoped as a low-privilege
account. The permission separation was deliberate. One debug step on one deploy day
undid it — and that step was made by the same engineer who is now up at midnight
writing a panicked draft to the CTO.

---

## Post-Mortem Notes (for defenders)

- **SSTI:** Use `render_template` with a static file. Never interpolate user input
  into a string passed to `render_template_string`.
- **Migration:** Finish it. An account on a weaker credential scheme in a table
  alongside stronger ones is not a minor inconsistency, it is the weakest link.
- **SQLi / table pivot:** Use parameterised queries. A WAF that blocks spaces is not
  a substitute for safe query construction.
- **Staff messages:** Internal communications stored in the same database as user
  data queryable by an unauthenticated endpoint is a design problem, not an
  implementation detail.
- **Upload:** Check only the final extension. Use `os.path.splitext(filename)[-1]`.
  Serve uploads from a path or origin that cannot execute code.
- **Key management:** The encrypted blob and its passphrase should not both be
  reachable by the same attacker through the same application. The encryption gave
  a false sense of safety.
- **Cron scripts:** Any script executed by a privileged cron job must be owned by
  root and not writable by anyone else. Debug permission changes must be reverted
  before the session ends, not before the next audit.
- **Privilege separation:** svc_admin's access scope was correctly designed. The
  failure was a single file permission, not a design failure. This is harder to
  prevent than a design flaw — it requires operational discipline at the moment of
  the change, not just at design time.
