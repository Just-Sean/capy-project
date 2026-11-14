# template/accounts/migrations/

**What it is:** the database changes for `accounts`. It holds one migration, `0001_initial.py`, which creates the `User` table.

**Why it ships with the starter:** every project starts with the same `User` table, and the starter's tests (`tests/test_migrations.py`) can check that the model and its migration match from the first run.

`__init__.py` is empty and makes the folder a package, which Django needs to find the migrations.
