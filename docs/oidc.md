# Single sign-on (OpenID Connect)

pomale can let people sign in through your own identity provider (Authelia, Authentik, Pocket ID, Keycloak, Zitadel, …) instead of, or in addition to, a pomale password. It is optional: without `OIDC_ISSUER` nothing changes.

- **Exactly one provider** per instance.
- **Accounts are linked by the provider's issuer and subject (`sub`), never by e-mail address.** An e-mail address that happens to match an existing account does not give access to it.
- **Roles stay in pomale.** The provider proves who someone is; admins decide in pomale who is an admin. Groups from the provider are not used.
- **Logging out of pomale does not log you out of the provider.**

## How it works

pomale uses the authorization code flow with PKCE (S256) and checks the result strictly:

- The discovery document's `issuer` must equal `OIDC_ISSUER` (a trailing slash does not matter).
- The ID token must be signed with an asymmetric key the provider publishes: RS\*, PS\*, ES\* or EdDSA. Tokens signed with HS256 (the client secret) or unsigned are refused.
- `iss`, `aud` (and `azp` with several audiences), `exp`, `iat` (60 s leeway), `nonce` and `sub` are checked. Claims from the userinfo endpoint are only used if they name the same subject.
- Every sign-in is bound to the browser that started it (a short-lived cookie) and can be used once, within 10 minutes.

pomale reads `email`, `preferred_username` and `name`, only to show which provider account is linked and to suggest a username. Nothing else from the provider is stored.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OIDC_ISSUER` | – (off) | The provider's issuer URL, e.g. `https://auth.example.org`. pomale reads `<issuer>/.well-known/openid-configuration`. |
| `OIDC_CLIENT_ID` | – | Required with `OIDC_ISSUER`. |
| `OIDC_CLIENT_SECRET` | – | For a confidential client (recommended). Empty: public client, PKCE only. |
| `OIDC_SCOPES` | `openid profile email` | Must contain `openid`. |
| `OIDC_LABEL` | – | Name on the button, e.g. `Authelia` → "Log in with Authelia". Empty: "Log in with single sign-on". |
| `OIDC_AUTO_CREATE` | `off` | `on`: anyone who can sign in at the provider gets a pomale account (role user) on their first sign-in. Use it when the provider already decides who may use pomale (e.g. a group restriction on the client). |
| `PASSWORD_LOGIN` | `on` | `off`: no passwords at all. Login, invitations and the first-run setup work only through the provider. |

**Redirect URI** to register at the provider: `https://<your PUBLIC_URL>/api/v1/auth/oidc/callback`

**Client settings at the provider:** authorization code flow, PKCE S256, token endpoint authentication `client_secret_basic` (or `client_secret_post`, or `none` for a public client), scopes `openid profile email`, ID tokens signed with RS256 or another asymmetric algorithm.

pomale does not contact the provider at startup; it starts even while the provider is down. If the provider uses a certificate from your own CA, mount the CA file into the container and set `SSL_CERT_FILE=/path/to/ca.pem`.

## Who gets an account

There are four ways to an account that signs in through the provider:

1. **Invitation.** The person opens the invitation link, chooses a username and clicks "Continue with …". The link is used up only when the sign-in succeeds.
2. **Linking an existing account.** Account page → "Sign-in" → "Link with …", confirmed with the pomale password. Afterwards both ways work.
3. **First-run setup.** The setup page offers "Continue with …"; the first admin account is then linked to the provider. With `PASSWORD_LOGIN=off` this is the only way.
4. **Automatically** with `OIDC_AUTO_CREATE=on`. The username comes from `preferred_username` or the e-mail address (a number is added if it is taken).

**Accounts without a password** (created through the provider) confirm sensitive changes, such as deleting the account or setting a password, by signing in at the provider again. pomale asks the provider for a fresh login (`prompt=login`) and checks `auth_time`. They can set a password on the account page later while `PASSWORD_LOGIN=on`.

**Unlinking.** People can remove the link themselves only while a password remains. Admins can remove an account's link (admin page → the account → "Remove provider link"); this logs the account out everywhere. Then create a recovery link: with it the person sets a password or links a provider account again.

**Changing `OIDC_ISSUER`** to another provider makes all existing links useless: the subjects belong to the old issuer. Link the accounts again (each person on the account page, or with recovery links).

**Locked out with `PASSWORD_LOGIN=off`** (provider gone)? Set `PASSWORD_LOGIN=on`, restart, and give the admin a password with `docker compose exec app python -m app.cli.create_user <name> --reset-password`.

## Provider examples

The examples assume pomale at `https://habits.example.org`. They were tested with Authelia 4.39, Authentik 2026.8 and Pocket ID 2.19; the CI runs against Dex.

### Authelia

```yaml
identity_providers:
  oidc:
    clients:
      - client_id: 'pomale'
        client_name: 'pomale'
        # authelia crypto hash generate pbkdf2 --variant sha512 --random --random.length 32
        client_secret: '$pbkdf2-sha512$310000$…'
        public: false
        authorization_policy: 'one_factor'   # or two_factor
        require_pkce: true
        pkce_challenge_method: 'S256'
        redirect_uris:
          - 'https://habits.example.org/api/v1/auth/oidc/callback'
        scopes: ['openid', 'profile', 'email']
        response_types: ['code']
        grant_types: ['authorization_code']
        token_endpoint_auth_method: 'client_secret_basic'
```

```env
OIDC_ISSUER=https://auth.example.org
OIDC_CLIENT_ID=pomale
OIDC_CLIENT_SECRET=<the secret before hashing>
OIDC_LABEL=Authelia
```

Authelia sends the e-mail address and username only through the userinfo endpoint; pomale reads it there. When pomale asks for a confirmation, Authelia asks for the password on its consent page.

### Authentik

Applications → Create with provider → **OAuth2/OpenID Provider**:

- Client type: **Confidential**. Redirect URI: `https://habits.example.org/api/v1/auth/oidc/callback` (strict).
- **Signing key: choose a certificate** (e.g. "authentik Self-signed Certificate"). Without one, Authentik signs ID tokens with HS256 and pomale refuses them.
- Scopes: `openid`, `email`, `profile` (the defaults). Grant type: authorization code.
- Restrict who may use pomale with a policy or group binding on the application if you use `OIDC_AUTO_CREATE=on`.

```env
OIDC_ISSUER=https://auth.example.org/application/o/<application slug>/
OIDC_CLIENT_ID=<client ID>
OIDC_CLIENT_SECRET=<client secret>
OIDC_LABEL=Authentik
```

### Pocket ID

Administration → OIDC Clients → Add OIDC Client: name `pomale`, **Confidential client**, callback URL `https://habits.example.org/api/v1/auth/oidc/callback`. Then open the client:

- **Access → Allowed user groups:** new clients are restricted to groups. Choose **All Users** or add the groups that may use pomale. Otherwise Pocket ID answers "You are not allowed to access this service".
- Enable **PKCE**.

```env
OIDC_ISSUER=https://id.example.org
OIDC_CLIENT_ID=<client ID>
OIDC_CLIENT_SECRET=<client secret>
OIDC_LABEL=Pocket ID
```

Pocket ID signs in with passkeys and shows a consent page ("Sign in to pomale") on each sign-in unless you turn on "Skip consent" for the client.

### Any other provider

Register a web application (confidential client) with the redirect URI above and the scopes `openid profile email`, and set `OIDC_ISSUER` to the URL in front of `/.well-known/openid-configuration`.

## iPhone home-screen app

The home-screen app has its own cookie storage. The sign-in at the provider opens inside the app and returns to it. This depends on iOS and the provider and has not yet been verified on a real device for every provider. If the app ends up in Safari instead, or you stay on the login page, use a pomale password in the home-screen app (keep `PASSWORD_LOGIN=on` and set one on the account page).

## Troubleshooting

The callback sends errors to the login page as a code in the address (`/login#error=…`); the page shows them translated. The server log has the details (`OIDC sign-in failed: …`).

| Code | Meaning |
|---|---|
| `oidc.provider_unavailable` | pomale cannot reach the provider (DNS, TLS, firewall, `SSL_CERT_FILE`). |
| `oidc.invalid_response` | The provider's answer failed a check: wrong issuer, audience, signature (HS256?), or a wrong client secret or redirect URI. |
| `oidc.state_invalid` | The sign-in took longer than 10 minutes, was finished in another browser, or reloaded after it was done. |
| `oidc.denied` / `oidc.provider_error` | The provider refused or the person cancelled. |
| `oidc.no_account` | No pomale account is linked to this provider account and `OIDC_AUTO_CREATE` is off: send an invitation. |
| `oidc.already_linked` | The provider account is linked to another pomale account. |
| `oidc.wrong_account` | A confirmation was done with a different provider account than the linked one. |
| `oidc.reauth_failed` | The provider did not ask for the login again although pomale asked it to (`auth_time` too old). |
