# template/templates/base.html

**What it is:** the base page for the site's own pages. The error pages extend it, and a project's pages can too. It's plain HTML with the browser's own styles, in **light or dark to match the visitor** (`<meta name="color-scheme" content="light dark">`). Restyle it with your own CSS or a theme app.

**Blocks:** `title` (default "Untitled page"), `head` (empty, inside `<head>` after the viewport tag: for stylesheets, meta tags and scripts; it comes before the default `color-scheme` tag, so a theme's own wins, since browsers use the first) and `content`, inside `<main>`.

**Keep it free of anything that needs the request, the user or the database:** no `{{ user }}`, no queries, not even `{{ csp_nonce }}`. `500.html` extends it, and Django shows that page when one of those may be what failed. For a nav bar or user menu:

1. Add a page that extends `base.html` (e.g. `layout.html`). It fills `head` with its stylesheets and any app tags that read the database (a theme app's, say). Pages extending it that add their own `<head>` tags start the block with `{{ block.super }}`, or they replace the layout's.
2. Have your other pages extend that one.

`500.html` keeps using the bare `base.html`.
