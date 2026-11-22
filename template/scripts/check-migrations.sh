#!/usr/bin/env bash
# Fail if a model change has no migration. Run by pre-commit and by hand.
set -euo pipefail
exec uv run python manage.py makemigrations --check --dry-run
