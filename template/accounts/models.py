import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """The project's user. Created before the first migration so it can grow later.

    Starts as Django's standard user (username, email, names, staff flags) with
    two changes:
      - email is required and unique regardless of letter case, and stored lowercase
      - public_id: a random UUID to show in URLs and APIs instead of the database id
    """

    email = models.EmailField("email address")
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        constraints = [
            # Backstop: Bob@x.com and bob@x.com can never both exist, even if
            # something writes to the database without going through save().
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique"),
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
