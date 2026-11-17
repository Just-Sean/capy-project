# template/tests/test_error_pages.py

**What it tests:** the error pages in `templates/`, using small test-only views that raise each error.

- **Each error** (400, 403, a failed form check, 404, 500) shows the site's own page with the right heading, and **no internal details**: a secret planted in the error message never appears.
- **A failed form check** explains what to do, and shows Django's reason **only with debug on**.
- An unknown host name gets the 400 page.
- **The 500 page works with the database and Redis both down.** This runs in a separate process with nothing reachable.
- A page that forgets its title still gets one, from `base.html`.
- **A page can add to `<head>`** through the `head` block, without editing `base.html`; a page extending a layout keeps the layout's tags with `{{ block.super }}`; and a theme's own `color-scheme` tag comes before the default one.
- **No page contains code the CSP would block:** no inline scripts or styles, `style=` or `on…=`.
- **The proxy's page stands on its own:** it's a complete page that loads nothing.
