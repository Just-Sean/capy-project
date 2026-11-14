# template/accounts/admin.py

**What it is:** the admin page for users. It builds on Django's own `UserAdmin`, so passwords, permissions and groups work as usual, with these additions:

- **List:** email, username, staff, active and date joined. Search covers email, username and names.
- **Edit page:** an extra "Identifiers" section showing `public_id`, read-only.
- **Add page:** asks for username, **email** and the password twice. Django's default add form doesn't ask for email, which the model requires.
