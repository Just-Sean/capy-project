# template/accounts/tests.py

**What it tests:** the `User` model.

- An email is stored trimmed and lowercase.
- Two users can't share an email in different cases. The test uses `.update()`, which skips `save()`, so it proves the **database constraint** works on its own.
- An empty email fails validation.
- Every user gets a different `public_id`.
- `create_superuser` makes a staff superuser.

It's named `tests.py`, Django's own style, and pytest finds it through `python_files` in `pyproject.toml`. The project-wide tests are in `tests/`.
