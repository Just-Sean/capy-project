# template/static/

**What it is:** the site's own static files (CSS, JavaScript, images), as opposed to each app's, which live in `<app>/static/<app>/`. `STATICFILES_DIRS` in `config/settings/files.py` points here; `collectstatic` gathers it with everything else in production, and development serves it straight from here.

| File | Job |
| --- | --- |
| `site.css` | The site's own styles, loaded by `base.html` on every page: for now only the skip link |
