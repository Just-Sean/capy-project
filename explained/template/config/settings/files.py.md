# template/config/settings/files.py

**What it is:** static files and uploaded files.

**Static files** (the admin's CSS and JS, and the project's own):

- They're collected into `staticfiles/` by `collectstatic` (the `Dockerfile` does this) and served by **WhiteNoise**.
- The storage is `CompressedManifestStaticFilesStorage`: compressed files with cache-busting names like `app.3f9a1c.css`.
- **Tests** use plain storage and serve straight from the apps, so no `collectstatic` is needed.

**Uploads, two kinds:**

| Storage | Address | Folder (filesystem) | Who can get a file |
| --- | --- | --- | --- |
| `default` (**private**) | `/media/...` | `media/` | Only whoever `can_download()` allows (`config/uploads.py`) |
| `public` | `/media-public/...` | `media-public/` | Anyone |

**Where uploads are kept** (`DJANGO_MEDIA_STORAGE`):

- **`filesystem`** (the default): this machine's disk. In production that's the `media` and `media_public` Docker volumes. An upload never replaces an existing file with the same name: it gets a new name.
- **`s3`:** S3 or any S3-compatible service (Cloudflare R2, Backblaze B2, MinIO...):
  - **`DJANGO_MEDIA_S3_BUCKET`** is required. `DJANGO_MEDIA_S3_REGION` and `DJANGO_MEDIA_S3_ENDPOINT_URL` are optional (the endpoint is for anything but AWS, and **must be `https://` in production**).
  - Private uploads go under `media/` in the bucket, public ones under `media-public/`. **All are private in the bucket**, with **signed links that expire after an hour**.
  - Files are never overwritten, and are always sent as downloads, so an uploaded HTML or SVG file can't run scripts.
  - **The keys never enter Django's settings.** boto3 reads `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the environment itself. Without them, the server's own role is used, which is safer than a long-lived key. Setting only one of the two is refused.
- **Anything else** is refused at start.

**`MEDIA_SENT_BY_PROXY`:** true only when `DJANGO_MEDIA_SENT_BY_PROXY` is on **and** uploads are on the filesystem. Then Caddy sends private files once the view allows them (`X-Accel-Redirect`). Caddy can't reach files in S3, so S3 always ignores this setting.

`PUBLIC_MEDIA_URL` and `MEDIA_URL` must match the Caddyfile's `/media-public/*` and `/media/*` routes.
