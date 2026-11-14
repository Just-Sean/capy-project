# template/tests/test_security_headers.py

**What it tests:** the security headers, the Content Security Policy and password hashing.

- **Headers everywhere:** pages, error pages, static files, and a refused form all send the security headers (`X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`).
- **The CSP:**
  - The policy is **exactly** the strict one (`EXPECTED_POLICY`), so a loosened rule fails.
  - Every response gets a new nonce.
  - The admin's pages contain nothing the policy would block.
- **Development:**
  - It only reports the policy, without enforcing it.
  - The debug page is what makes reporting necessary.
  - It serves static files the way production does, through WhiteNoise.
- **HSTS:**
  - It's sent over HTTPS only.
  - Production sends it for a year, subdomains included, **without preloading**. A project that opts in to preloading changes this test.
- **Passwords:**
  - Production hashes them with Argon2, and `argon2-cffi` is a production dependency, not a dev tool.
  - An older hash still works and gets upgraded at login.
