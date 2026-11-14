# template/templates/base.html

**What it is:** the base page for the site's own pages. The error pages extend it, and a project's pages can too. It's plain HTML with the browser's own styles, in **light or dark to match the visitor** (`<meta name="color-scheme" content="light dark">`). Restyle it with your own CSS or a theme app.

**Blocks:** `title` (default "Untitled page") and `content`, inside `<main>`.

**Keep it free of anything that needs the request, the user or the database:** no `{{ user }}`, no queries, not even `{{ csp_nonce }}`. `500.html` extends it, and Django shows that page when one of those may be what failed. For a nav bar or user menu:

1. Add a page that extends `base.html` (e.g. `layout.html`).
2. Have your other pages extend that one.

`500.html` keeps using the bare `base.html`.
