# NexQR

A Django QR workspace with account-specific saved links, basic request counts and browser-encrypted messages. The responsive interface uses local assets. This is a small application with operator-created accounts, not a turnkey public SaaS.

## Local setup

Requires Python 3.12+. In PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
# Put the generated value in .env as SECRET_KEY. Keep DEBUG=True locally.
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser
.venv/Scripts/python manage.py runserver 127.0.0.1:8000
```

On macOS/Linux use `.venv/bin/python`. Sign in at `/accounts/login/`; operators create additional users in `/admin/`. No open registration. A unique secret and explicit allowed hosts are required. `.env` is excluded from Git and Docker images.

## Features and limits

- **Standard:** direct HTTP(S) link and PNG download; no saved record.
- **Dynamic:** creator-owned saved link with request counts. Redirects remain public for scanning. Destination editing is available to trusted operators in Django admin, not in the dashboard.
- **Protected message:** new messages use browser Web Crypto, AES-256-GCM, PBKDF2-SHA256 with 600,000 iterations, random 16-byte salts and 12-byte nonces. Passwords are not submitted. This requires a trusted server and strong password; it is not an independently audited secret-sharing service. Legacy CryptoJS messages still open with a warning about absent tamper detection.
- **Artistic:** optional staff-only preview, disabled by default. Set a Replicate token, compatible 64-character QR model version and `ARTISTIC_ENABLED=True`. A database-backed global daily attempt limit defaults to 2 (hard maximum 10); failures consume attempts. Prompts and QR links go to Replicate; charges may apply. The provider receives a one-minute cancellation deadline. Local deadlines are checked between network operations with socket/response limits, not a hard process deadline. Check QR scan reliability before sharing.
- **Extension:** load `extension/` unpacked in Chrome. Clicking opens the signed-in local dashboard with the active page prefilled. Creation requires form submission. The old anonymous API is retired; the extension has no network host permission.

Only the owner can view a saved QR or its analytics in the normal dashboard. Creation requires authentication and CSRF validation, with 100 attempts per user per UTC day. New scan records retain only a coarse device category, not IP addresses or complete user agents. Counts include repeat requests and bots, not unique visitors or verified camera scans. No legal compliance claim is made.

## Existing installations

Back up the database before `migrate`. Migration 0004 adds ownership and daily budgets. **Existing QR records remain unassigned** and their public links still work. In trusted Django admin, assign each record to its verified owner. Nobody automatically inherits legacy records; normal staff dashboards have the same owner filter. Admin permissions intentionally allow administrative access. Historical IP/user-agent data remains in the database; review retention for your deployment.

Rotate the old shared default secret to a generated one; current login sessions will end. Message encryption does not depend on the Django secret. Keep backups and secrets outside version control.

## Deployment

For local containers, set an alphanumeric `POSTGRES_PASSWORD` in `.env`, run `docker compose up --build`, then `docker compose exec web python manage.py createsuperuser`. The exposed port is loopback-only. Back up the database volume. Migrations/static collection run at startup; use a controlled release step for multiple production instances.

Public hosting needs `DEBUG=False`, explicit hosts, HTTPS and a configured trusted reverse proxy. Do not blindly trust forwarded headers. Add edge login/redirect rate limits, monitoring and backups appropriate to actual traffic. Daily creation budgets do not replace those controls. Run `manage.py check --deploy` with production settings. Repository updates do not automatically migrate or reconfigure an existing deployment.

HSTS applies to the configured host. Subdomain HSTS and preload remain opt-in deployment decisions; the corresponding Django deployment warnings are expected until the operator verifies every affected subdomain.

## Verification

```sh
python manage.py test
python manage.py makemigrations --check --dry-run
node --test tests/crypto.cjs
```

CI covers ownership, CSRF, anonymous access, legacy migration, budgets, provider failures, actual PNG output and encryption failures on Windows/Linux and PostgreSQL. Provider fixtures incur no charges; live model availability and artistic scan quality remain unverified. Browser checks cover sign-in, generation, protected messages and narrow layouts.

Legacy decryption uses vendored [CryptoJS 4.2.0](https://www.npmjs.com/package/crypto-js/v/4.2.0), with its license in `static/vendor/`. New encryption uses Web Crypto. The optional integration follows the [Replicate HTTP API](https://replicate.com/docs/reference/http). MIT licensed.
