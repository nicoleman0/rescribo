# Design

## Context

Two parsers can supply the key, and they disagree.

- Local `task api` and `task worker`: `environ.Env.read_env(BASE_DIR / ".env")` in `backend/config/settings.py` (django-environ 0.14.0). Tested on 15 Oct with a generated RSA key in PKCS#1 and PKCS#8:
  - Unquoted, single-quoted, and double-quoted one-line values all arrive with literal `\n`. `read_env` keeps `\n`, `\r`, and `\t` escaped inside double quotes (`_keep_escaped_format_characters`). Each loads once `\n` becomes a newline.
  - A double-quoted multi-line value arrives as its first line only, with the opening quote: `"-----BEGIN RSA PRIVATE KEY-----`. `read_env` logs every other line at WARNING as `Invalid line: <line>`, which prints key material to stderr before Django configures logging.
  - The `ValueError` in the issue is from `serialization.load_pem_private_key` in `create_app_jwt` (`client.py`), not from django-environ.
- Production: Compose reads `.env.production` through `env_file:` (`compose.prod.yaml`); `.env*` is in `.dockerignore`, so `read_env` finds nothing in the image. Per the [Compose docs](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/), double-quoted values process `\n` into newlines, unquoted and single-quoted values keep `\n` literally, and single-quoted values may span lines. This is from the docs; the Compose parser was not run during planning.

So the one-line form works under both parsers once the loader unescapes `\n`, whatever the quoting. Real newlines arrive from a shell (`"$(cat key.pem)"`) or a Compose multi-line value.

## Goals / Non-Goals

**Goals:**
- One loader in `integrations/github_app/` that owns the accepted forms and the validation.
- Every process that loads Django settings fails fast on a bad key.

**Non-Goals:**
- A key-file variable (maintainer decision).
- Changing `create_app_jwt` or `github_client()`. They keep parsing the PEM text per call.
- Silencing django-environ's `Invalid line` warnings. See Risks.

## Decisions

- **New module `backend/integrations/github_app/private_key.py`** with `load_private_key(value: str) -> str`. It strips surrounding whitespace, returns `""` for an empty result, replaces literal `\r\n` and `\n` with a newline, then calls `serialization.load_pem_private_key(..., password=None)` and requires an `rsa.RSAPrivateKey`. It returns the unescaped PEM text so the rest of the code keeps reading a string setting.
  - Replacing `\n` is safe because base64 and PEM armour never contain a backslash.
  - It catches `ValueError`, `TypeError` (encrypted key), and `UnsupportedAlgorithm`, and raises `django.core.exceptions.ImproperlyConfigured` with `from None` so no key bytes travel in the chain. The message: `RESCRIBO_GITHUB_PRIVATE_KEY is set but is not an unencrypted RSA private key in PEM format. Use the PEM file's text with real newlines, or one line with \n between the PEM lines. See docs/SETTINGS.md.`
  - Alternative: `env.str(..., multiline=True)` already unescapes `\n`. Rejected: it splits the accepted-form rule between settings and the integration, and it does not validate.
  - Alternative: a Django system check or an `AppConfig.ready()`. Rejected: system checks do not run under Celery or gunicorn, and `integrations` is not an installed app.
- **`settings.py` calls the loader on the one line it owns:** `RESCRIBO_GITHUB_PRIVATE_KEY = load_private_key(env("RESCRIBO_GITHUB_PRIVATE_KEY", default=""))`, with one import at the top. Settings import time is startup for runserver, gunicorn, Celery worker and beat, and `manage.py`. Importing `integrations.github_app` at settings time is safe: the package imports no Django models or settings.
- **Tests generate keys at runtime** with `cryptography`. No key fixture is committed.
- **Env-file tests use the exact lines documented** in `docs/SETTINGS.md` and `.env.production.example`, written to a temporary file and read with `environ.Env.read_env` into a patched `Env.ENVIRON` dict, so `os.environ` is untouched.
- **One subprocess startup test** runs `django.setup()` with a bad key in the environment and asserts a non-zero exit, the variable name in stderr, and no key text in stderr. It proves the failure happens at settings load, not only in the unit.
- **No ADR.** The decision is small and lives in `docs/SETTINGS.md` and this change.

## Risks / Trade-offs

- [A multi-line value in `.env` leaks key lines to stderr through django-environ's `Invalid line` warnings, before the loader runs] → Docs say to use the one-line form in `.env`. The loader then fails startup on the truncated first line. Suppressing the warning means changing the shared `read_env` line; that is a question for the maintainer.
- [Compose behaviour is from its docs, not a run] → The documented one-line form is unquoted, which Compose and django-environ both pass through unchanged; the loader handles the rest.
- [A deployment with a bad key that never used GitHub now fails to start] → Intended. The message says what to fix, and an empty value still starts.

## Migration Plan

None. Valid multi-line keys keep working. Rollback is a revert.
