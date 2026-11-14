# template/tests/test_uploaded_files.py

**What it tests:** the upload storage settings in `config/settings/files.py`. Most checks start `manage.py` with different environment variables, since storage is set when settings load.

**Local storage (the default):**

- Uploads are stored on this machine.
- An upload never replaces an existing file, and can't escape the media folder.
- Private uploads always go through the check. **Only development** serves public ones itself.
- Public uploads have their own folder and address.
- Caddy sends private files only when they're on this machine's disk, never with S3.

**S3:**

- Public uploads go under their own folder, with signed links too.
- Files are private downloads that are never overwritten.
- Links are signed (SigV4) and expire after an hour.
- **Keys come from the environment and never appear in Django's settings.** Without keys, the server's role is used.
- **Bad settings are refused:**
  - an unknown storage
  - a missing or blank bucket
  - an endpoint that isn't a full URL
  - plain `http://` in production
  - only one of the two keys

  An `HTTPS://` endpoint in capitals is accepted, and outside production a local test service may use plain HTTP.

The S3 checks run without the internet: they build links and settings but never contact S3.
