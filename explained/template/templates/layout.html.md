# template/templates/layout.html

**What it is:** the site's own layout. It extends `base.html`, and the site's pages and plugged-in apps (modules made from capy-module) extend it. **It's the project's file:** Copier makes it with the project, or adds it on update if it's missing (`_skip_if_exists` in `copier.yml`), and `copier update` never changes it after that.

**What a page fills:** only `title` (always), `head` (starting with `{{ block.super }}`, so the layout's own head tags stay) and `content`. The project fills the rest here.

**What's in it:**

- **`<header>`** with a comment where the nav bar goes, and **Django's messages** in a `<div role="status">`. The region is always there, even empty, so screen readers announce a message added without a page reload (htmx, JavaScript). Messages added inside it are announced; replacing the whole region silences screen readers. Modules rely on it ("Saved." after a form), so keep it, and never name a template variable `messages`: a page's own `messages` would replace Django's in the region.
- **Comments marking where shell-type modules plug in** (a theme, an app shell): attributes on `<html>` (the `html_attrs` block, whose line starts with a space since it follows `lang="en"`), the page's head, and the nav. Each such module's README names the one line to add. They're comments, not real tags, so the layout renders in every project, with or without modules, and loads no tag library.
- **No footer** until the project adds one (fill the `footer` block with a `<footer>`): an empty `<footer>` is an empty landmark for screen readers.

**Why not in `base.html`:** shell modules' tags read the database, and the 500 page uses the bare `base.html` when the database may be down. So everything that needs the request, the user or the database goes here.

**Tested by** `tests/test_layout.py`: a page filling the three blocks; the messages region (with and without messages, shown once, in order and escaped); a theme's `html_attrs` on `<html>`, a nav link and wrapped messages in an edited stand-in layout; and the error pages staying on `base.html`. The tests check the project's own edited `layout.html` too, so a missing messages region fails them.
