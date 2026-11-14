# template/tests/test_ignore_files.py

**What it tests:** no secret file reaches git or the Docker image.

- **Git:** for a list of sample secret files, `.gitignore` must ignore each one:
  - `.env`, `.env.local`, `config/.env`, `.envrc`
  - private keys and certificates
  - SSH keys
- **`.env.example` is kept:** git must not ignore it.
- **The image:** `.dockerignore` must leave out every `.env` file, `.env.example` included.
- **Every folder:** each secret rule in `.dockerignore` must start with `**/`, or Docker would only match the top folder.

It asks **git itself** (`git check-ignore`) in a throwaway repository, with the user's own git settings switched off, so the answer is what git really does. That covers `.dockerignore` too, since Docker's rules are close enough to git's for these patterns.
