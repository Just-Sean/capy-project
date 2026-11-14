# copier.yml

**What it is:** Copier's settings for this template. Copier reads it when you run `copier copy` or `copier update`.

**What's in it:**

- `_min_copier_version: "9.4"`: older Copier versions refuse to use the template.
- `_subdirectory: template`: only files under `template/` go into new projects. The repo's own README, `.gitignore`, hook and `explained/` stay behind.
- **Two questions:**

| Question | Default | Used for |
| --- | --- | --- |
| `project_name` | `My Project` | The README's title and the `description` in `pyproject.toml` |
| `project_slug` | The name, lowercased, with spaces and dashes as `_` | The Python project name, the database name, the Compose project names (`<slug>` and `<slug>-production`), the image names (`<slug>-web`, `<slug>-caddy`) and the backup folder |

The slug's validator only accepts a lowercase letter followed by lowercase letters, digits and underscores, so it's always safe in file names, database names and Docker names.

Copier saves the answers in the project's `.copier-answers.yml` (made from `template/{{_copier_conf.answers_file}}.jinja`), so `copier update` doesn't ask again.
