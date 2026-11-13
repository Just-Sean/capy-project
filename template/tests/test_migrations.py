"""Every model change has its migration."""

from io import StringIO

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_migrations_are_up_to_date():
    # Fails if a model changed without `makemigrations`: the change would never
    # reach the database, in development or in production.
    output = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=output)
    except SystemExit:
        pytest.fail(f"A model changed without a migration:\n{output.getvalue()}")
