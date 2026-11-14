# template/config/uploads.py

**What it is:** everything about **private uploads**. Uploads are private by default: nothing serves their folder directly. A file's address (`/media/<name>`, what a field's `.url` gives) comes to the view here, which decides who gets it.

**What a project uses from it:**

| Name | What it is |
| --- | --- |
| `can_download(user, name)` | **The rule a project changes.** It decides whether this user may have this file (`name` is the stored name, e.g. `3f9a.../report.pdf`). By default, only active staff can. A real project usually checks ownership, e.g. that a `Document` with this file belongs to the user |
| `random_folder` | An `upload_to` for file fields that puts each file in its own random folder (`<uuid>/<filename>`), so names never collide and one address doesn't hint at another |
| `public_storage` | The storage for files **anyone** may see: `FileField(storage=public_storage)`. It's a function, so migrations record its name instead of this machine's folder |

**The view, `download(request, name)`:**

1. It answers `GET` and `HEAD` only (`@require_safe`).
2. **It refuses odd names** (`is_plain_name`): empty, `.` or `..` parts, such as `a//b` or `alice/../bob/x.pdf`. Otherwise `can_download()` could approve one path while a different file gets sent.
3. It asks `can_download()`, then checks the file exists. A name outside the uploads folder (`SuspiciousOperation`) counts as not allowed.
4. **Anyone not allowed gets a 404,** the same as for a missing file, so nobody learns which files exist.
5. If allowed, the file goes out one of two ways:
   - **Behind Caddy** (`MEDIA_SENT_BY_PROXY`, production with Docker): an empty response naming the file in `X-Accel-Redirect`. Caddy then sends the file from the `media` volume itself, so no Gunicorn worker is tied up streaming it.
   - **Otherwise** (development, tests, a server without Docker): Django sends the file itself (`FileResponse`). A folder, or a file deleted just then, gives a 404.
6. Either way, `DOWNLOAD_HEADERS` are added:
   - `Content-Disposition: attachment`: always a download.
   - `Content-Security-Policy: default-src 'none'; sandbox`: an uploaded HTML or SVG file can't run scripts on the site.
   - `Cache-Control: private, no-store`: no cache keeps the file, not even the browser's.

   Caddy's `(download_headers)` snippet must match them.

**With S3 storage**, a field's `.url` is a signed link straight to the bucket that expires after an hour, so requests never reach this view and `can_download()` doesn't apply (see `settings/files.py`). **Anyone holding a link can download the file until it expires**, so only show a private file's link to those allowed to see it.

**Checked by:** `tests/test_private_uploads.py`.
