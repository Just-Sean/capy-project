# template/tests/test_private_uploads.py

**What it tests:** the private download view in `config/uploads.py`, using a temporary uploads folder.

**Who gets a file:**

- Active staff get it, as a download that no cache keeps.
- **Everyone else gets a 404:** visitors, ordinary users, and inactive staff.
- **Even staff get a 404** for a missing file, a folder, a name outside the uploads folder, or a name with `.`/`..` or empty parts.
- **Dot parts can't get past a rule on the name.** With a sample "owner's folder" rule in place of `can_download()`, `alice/../bob/x.pdf` still can't fetch Bob's file.
- A file deleted while it's being fetched gives a 404, not a crash.
- Only `GET` and `HEAD` are answered.

**Behind Caddy** (`MEDIA_SENT_BY_PROXY`):

- The app only names the file in `X-Accel-Redirect`, and doesn't send it.
- Others still get a 404.

**The helpers:**

- `random_folder` gives each file its own unguessable folder.
- `public_storage` saves to the public folder, not the private one.
- A migration records `public_storage` by name, not this machine's folder path.
