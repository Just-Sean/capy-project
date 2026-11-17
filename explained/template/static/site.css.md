# template/static/site.css

**What it is:** the site's own stylesheet, linked from `templates/base.html` on every page. A file rather than inline styles, because the Content Security Policy blocks inline ones.

**What it does:** hides the "Skip to the main content" link off screen until it gets keyboard focus, then shows it at the top left in the page's own colors (`Canvas` and `CanvasText`, so it reads in light and dark), with a border and a visible outline. It's moved off screen rather than `display: none`, which would hide it from screen readers too.

Add the site's own styles here, or in more files next to it.
