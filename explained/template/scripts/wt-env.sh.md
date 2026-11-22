# template/scripts/wt-env.sh → scripts/wt-env.sh

**What it is:** the first thing to run inside a fresh git worktree (`claude -w <name>`), so each parallel agent gets its own virtualenv and its own dev-server port.

**What it does:** runs `uv sync`, then gives the worktree a unique `PORT` in its `.env` so two agents don't fight over the dev server. It also carries a commented block for giving each worktree its **own database** — uncomment it once your settings read `DB_NAME` from the environment, so parallel agents don't write to each other's data.

**Why:** git worktrees isolate files, not running processes or databases; this closes that gap. In a new worktree, run `scripts/wt-env.sh` before starting work. See the README's multi-agent notes.
