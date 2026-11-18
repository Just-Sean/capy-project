# template/tests/test_layout.py

**What it tests:** `templates/layout.html`, with a test-only page written the way a plugged-in app writes one (filling only `title`, `head` and `content`). The file is also the tests' URL map: the test pages plus the project's own URLs, so a nav link (`{% url %}`) in the layout works; and the tests may use the database, since a theme module's lines read it.

- **The page fills the layout:** its title is in `<title>`, its script is in `<head>` after the layout's own head tags (`{{ block.super }}`), and its content is inside the one `<main>`.
- **Messages:** "Saved." shows in the `role="status"` region (found with an HTML parser, so any element, any attributes, and messages wrapped in their own elements all work), which is inside `<header>`, before `<main>`; the region is there (empty) without messages; a message shows only once; several show in order, escaped (HTML in a message is shown as text); and a message pending when an error page shows waits for the next page.
- **An edited layout:** a stand-in layout with a nav link, a theme's `html_attrs` line (starting with a space, which lands on `<html>`), messages each in their own `<div>` with an icon, and a footer, passes the same checks.
- **The error pages stay on the bare `base.html`,** never `layout.html`, so the 500 page works with the database down. The check reads each page's first `{% extends %}` (a comment before it is fine) and names the page if it's wrong.

These checks hold for the project's own edited `layout.html` too (a theme module's lines, a nav, a footer), so they keep checking what modules rely on.
