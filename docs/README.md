# CAPA Configuration

## Required environment variables

| Variable | Description |
| --- | --- |
| `SECRET_KEY` | Session signing key used by the auth system. Can be long. |
| `AUTH_ENABLED` | Enables authentication (set to `true`/`false`). |
| `DEV_MODE` | Enables developer defaults and tooling (set to `true`/`false`). |

## Admin seeding environment variables

| Variable | Description |
| --- | --- |
| `ADMIN_USERNAME` | Admin username for bootstrapping. Defaults to `admin` only when `DEV_MODE=true`. |
| `ADMIN_PASSWORD` | Admin password for bootstrapping. Defaults to `admin123` only when `DEV_MODE=true`. Must be 72 bytes or fewer for bcrypt. |

### Production behavior (`DEV_MODE=false`)

Admin seeding only occurs when both `ADMIN_USERNAME` and `ADMIN_PASSWORD` are explicitly provided. `SECRET_KEY` is only used for session signing and is never used as an admin password.
