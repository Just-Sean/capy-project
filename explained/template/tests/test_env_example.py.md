# template/tests/test_env_example.py

**What it tests:** `.env.example` lists every environment variable the project reads, and nothing else. It works by scanning the code:

- **Python files:** `env(...)`, `env.bool(...)`, `os.environ...` and the like, skipping comments, tests, migrations and virtualenvs.
- **Compose files:** `${VAR}`, skipping the `$$VAR` that Compose passes to the container.

**The checks:**

- Every variable the project reads is listed, and every listed variable is read somewhere.
- Each variable is listed once.
- Every line is blank, a comment, or a plain `NAME=value`: no indents, spaces, quotes or comments in the value, which django-environ would misread.
- Each listed variable really loads once its line is uncommented.
- `DJANGO_ENV` shows a real environment.
- True/false values are words django-environ knows.

**Testing its own scanners:** about half the file tests the scanners themselves, on sample text: reads they must find, look-alikes they must ignore, unusual line breaks, files that can't be read, and declared encodings. A broken scanner can't then pass silently by finding nothing.
