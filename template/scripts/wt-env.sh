#!/usr/bin/env bash
# wt-env.sh — run once inside a fresh git worktree before an agent starts work.
# Gives the worktree its own virtualenv and its own dev-server port so parallel
# agents don't collide on it.
set -euo pipefail
uv sync
if [ -f .env ]; then
  name=$(basename "$PWD" | tr -c 'a-z0-9\n' '_')
  port=$(( 8001 + $(printf '%s' "$name" | cksum | cut -d' ' -f1) % 900 ))
  if grep -q '^PORT=' .env; then
    sed -i -E "s/^PORT=.*/PORT=${port}/" .env
  else
    printf 'PORT=%s\n' "$port" >> .env
  fi
  # This project shares one Postgres container across worktrees (COMPOSE_PROJECT_NAME
  # in .env keeps them on the same container). To stop parallel agents writing to each
  # other's data, give each worktree its OWN database — uncomment once your settings
  # read DB_NAME from the environment:
  #   sed -i -E "s/^DB_NAME=.*/DB_NAME=app_${name}/" .env
  #   docker compose exec -T db createdb -U postgres "app_${name}" 2>/dev/null || true
  #   uv run python manage.py migrate
  echo "worktree=${name} port=${port} (.env updated; set DB_NAME too if you share one DB)"
else
  echo "worktree ready (uv sync done)"
fi
