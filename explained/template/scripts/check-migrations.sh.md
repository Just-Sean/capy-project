# template/scripts/check-migrations.sh → scripts/check-migrations.sh

**What it is:** a tiny script that fails if a model change has no migration (`uv run python manage.py makemigrations --check --dry-run`).

**Why:** it's wired into `.pre-commit-config.yaml` as the `django-missing-migrations` hook, so a commit that changes models without generating a migration is blocked — the mistake that most often trips up parallel agents. Run it by hand any time with `scripts/check-migrations.sh`.
