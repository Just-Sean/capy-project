# template/tests/test_migrations.py

**What it tests:** every model change has its migration. It runs `makemigrations --check`, which never writes a file and fails if a model changed without a migration. That catches a forgotten `makemigrations` before it reaches production, where the `migrate` step would have nothing to apply.
