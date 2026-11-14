# template/accounts/

**What it is:** the Django app that holds the project's custom `User` model (`AUTH_USER_MODEL = "accounts.User"`).

**Why it exists from day one:** Django can't easily switch to a custom user model after the first migration. Starting with one, even a nearly standard one, means the project can add fields to users later.

| File | Purpose |
| --- | --- |
| `models.py` | The `User` model |
| `admin.py` | The user admin, with email and `public_id` |
| `apps.py` | The app's config |
| `migrations/` | The `User` table, shipped with the starter |
| `tests.py` | The model's tests |
| `__init__.py` | Empty; makes the folder a Python package |

Other apps should refer to users as `settings.AUTH_USER_MODEL` (in models) or `get_user_model()`, never by importing `accounts.models` directly. That way a reusable app works in any project.
