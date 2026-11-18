# template/tests/test_layout.py

**What it tests:** `templates/layout.html`, with a test-only page written the way a plugged-in app writes one (filling only `title`, `head` and `content`).

- **The page fills the layout:** its title is in `<title>`, its script is in `<head>` after the layout's own head tags (`{{ block.super }}`), and its content is inside the one `<main>`.
- **Messages:** "Saved." shows in the `role="status"` region (any element, any other attributes), which is inside `<header>`, before `<main>`; the region is there (empty) without messages; and a message shows only once.
- **The error pages stay on the bare `base.html`,** never `layout.html`, so the 500 page works with the database down.

These checks hold for the project's own edited `layout.html` too (a theme module's lines, a nav, a footer), so they keep checking what modules rely on.
