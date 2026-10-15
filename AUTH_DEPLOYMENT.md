# Server authentication – activation pending

Owner recovery mailbox: `tomas_kybartas@yahoo.com` (confirmed by owner).

## Implemented

- Separate administrator and shared team passwords; salted scrypt hashes are held only in SQLite.
- Opaque 24-hour HttpOnly, Secure, SameSite=Strict session cookies; only token hashes are stored.
- Changing the shared password atomically revokes every team session. Already open pages check the server every 15 seconds and lock when validation fails. Server asset/API access is rejected immediately.
- Owner can revoke all team sessions without changing the shared password. Anyone who still knows that password can sign in again; change it for lasting revocation.
- Owner changes their own password after entering their current password; administrator sessions and reset links are revoked.
- Recovery / initial owner setup sends a random, single-use, 15-minute link exclusively to the fixed owner mailbox. The email address in a client request cannot change the recipient.
- Reset tokens and session cookies are never returned by logging. Reset tokens use a URL fragment, cleared by the client before use, and no-referrer headers.
- Same-origin JSON POST enforcement, persistent rate limits, protected calculator scripts, and an explicit public-file allowlist.
- Existing statically hosted calculator remains unchanged until deployment and cutover.

## Required before activation

1. Owner approves a paid Render web service with a 1 GB persistent disk, or chooses an alternative durable database/hosting provider. Do not use an ephemeral disk for authentication state. Current published Render rate is $7/month compute plus $0.25/month per GB disk, excluding tax/usage.
2. Provision a transactional email sender (Resend supported). The recipient Yahoo mailbox does not need its password shared. Configure an API key and verified sender directly as secret environment variables in Render; never paste credentials in chat or commit them.
3. Run Node 24+, build command `node --version`, start command `npm start`. Set `AUTH_DB_PATH=/var/data/auth.sqlite`, `PUBLIC_ORIGIN` to the exact canonical HTTPS origin without trailing slash, `RESEND_API_KEY`, and `MAIL_FROM`. Mount persistent storage at `/var/data`. Single instance only for this SQLite setup. No third-party npm dependencies are required.
4. Owner uses recovery to initialize the administrator password, then sets the first shared team password. The owner enters all new authentication values themselves using the secure UI. No default shared or administrator password is embedded.
5. Test actual recovery email delivery, password reset, independent admin/team sessions, browser lockout and restart persistence on the deployed origin.
6. Migrate the original static site: redirect/retire its publicly served calculator scripts; do not leave the old site as a working bypass. Preserve users' browser-local projects and saved examples during origin migration using a reviewed export/import path before retiring the old origin. New server hosting cannot inherit localStorage from a different onrender.com origin.
7. Only then announce activation to the owner. Keep the live calculator available during preparation.

## Practical boundary

This controls access to the hosted application. It cannot retract JavaScript/calculator copies a recipient has already downloaded, or erase their saved local data. The GitHub repository must also have appropriate visibility/access if preventing source redistribution matters. It is not DRM. Move calculations to server endpoints if the business requires stronger enforcement than hosted-page access.

## Verification

`node --test tests/auth.test.mjs tests/auth-http.test.mjs`

Tests cover bootstrap, persistent sessions, old-password rejection, shared/admin isolation, session revocation, password changes, single-use/expired reset links, token expiry, rate limits, HTTP origin checks, source-file denial, protected assets, cookies, logout and unconfigured mail delivery.

Existing calculator, tax, saved-example, storage and scale tests also pass. Real mail delivery and production browser QA are pending credentials and deployment. No authentication deployment has been activated.
