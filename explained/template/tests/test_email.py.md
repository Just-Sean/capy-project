# template/tests/test_email.py

**What it tests:** email in each environment, mostly by starting `manage.py` with different `EMAIL_URL`s, since email is set when settings load.

- **Tests** keep emails in memory, and ignore a real mail server set in `.env`.
- **Development:**
  - It prints emails to the console.
  - It may use a local mail catcher over plain `smtp://`.
  - It refuses a login over plain SMTP.
- **Production without email:** it starts and passes `check --deploy`, but sending (`sendtestemail`) fails with "Email isn't set up".
- **Production with email:**
  - `smtp+tls://` and `smtp+ssl://` give the right server, port, login, encryption and 10-second timeout.
  - Encoded characters in the password are decoded.
- **Refused:**
  - plain SMTP in production
  - a missing From address
  - a missing server
  - an unknown scheme
  - **a URL that a password with unencoded characters cut short**, refused **without the password showing in the error**
