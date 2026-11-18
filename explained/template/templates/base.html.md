# template/templates/base.html

**What it is:** the bare page under every page. The error pages extend it directly; the site's own pages and plugged-in apps extend `layout.html`, which extends it. It's plain HTML with the browser's own styles, in **light or dark to match the visitor** (`<meta name="color-scheme" content="light dark">`). Restyle it with your own CSS or a theme app.

**Structure:** a "Skip to the main content" link first (hidden by `static/site.css` until it's focused), then the `header` block, `<main id="main" tabindex="-1">` (so focus moves there reliably, iOS included) with the `content` block, and the `footer` block. So a site's header, nav and footer are landmarks of their own, outside `<main>`, and keyboard users can jump past the nav. It loads `static/site.css` on every page.

**Blocks:** `html_attrs` (empty, on the `<html>` element: for attributes a theme module adds through `layout.html`; the error pages leave it empty), `header` and `footer` (empty, outside `<main>`), `title` (default "Untitled page"), `head` (empty, inside `<head>` after the `site.css` link: for stylesheets, meta tags and scripts; it comes before the default `color-scheme` tag, so a theme's own wins, since browsers use the first) and `content`, inside `<main>`.

**Keep it free of anything that needs the request, the user or the database:** no `{{ user }}`, no queries, not even `{{ csp_nonce }}`. `500.html` extends it, and Django shows that page when one of those may be what failed. The nav bar, Django's messages and shell modules' tags (a theme's, which read the database) go in `layout.html` instead (see `layout.html.md`); `500.html` keeps using the bare `base.html`.
