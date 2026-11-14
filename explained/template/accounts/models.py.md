# template/accounts/models.py

**What it is:** the project's `User` model. It's Django's standard user (`AbstractUser`: username, email, names, staff flags, password) with two changes.

**1. Email is required and unique, whatever its letter case:**

- `email` is redefined without `blank=True`, so forms and `full_clean()` require it.
- `save()` trims it and stores it lowercase.
- A database constraint, `accounts_user_email_ci_unique` on `Lower("email")`, is the backstop: `Bob@x.com` and `bob@x.com` can never both exist. That holds even when something writes to the database without `save()`, such as `.update()`.

**2. `public_id`:** a random UUID, unique and not editable. Show it in URLs and APIs instead of the database `id`, so addresses don't reveal how many users there are or let anyone guess the next one.

`__str__` shows the email.

**What it doesn't change:** login is still by **username** (`USERNAME_FIELD` is Django's default). A project that wants email login changes that itself.
