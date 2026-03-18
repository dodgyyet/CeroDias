# CeroDias: The Incident

## Background

CeroDias Enterprise Solutions runs a Flask-based customer portal for IT certification
vouchers. The engineering team is small: developers who know each other, move fast,
and trust each other's judgment. There is no dedicated security team. Audits happen
when someone schedules them.

This is not a story about obvious negligence. Each of the four issues described below
is the kind of thing that can sit in a codebase or a database for months without
triggering any alert, any failed test, or any visible symptom. None of them are
"someone left the door open." They are the ordinary residue of a team that ships
quickly and cleans up later.

---

## The People

**k.chen** - backend engineer. Careful with production systems. Uses the internal
staff messaging system for quick operational notes, the same way most developers use
Slack. Assumes the messaging system is private.

**j.harris** - full-stack developer, joined during the original build-out. Handles
the customer portal. Their account was flagged for a credential migration eight months
ago. The ticket is still open.

**svc_admin** - the deployment service account. Owns the SSH private key used by the
automation pipeline.

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
ssh -i id_rsa svc_admin@<server>
```

Shell.

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
Remove any one of these and the chain does not complete.

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
