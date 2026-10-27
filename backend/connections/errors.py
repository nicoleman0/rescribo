"""Safe connection errors shared by provider adapters and HTTP handlers."""

from urllib.error import URLError

import httpx
from slack_sdk.errors import SlackApiError

from accounts.demo import DEMO_DETAIL
from integrations.github_app.client import GitHubAPIError


class SetupError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


def known_error(code: str) -> SetupError:
    """An error whose detail is the stored next step, so the two never drift."""
    return SetupError(code, ERROR_DETAILS[code])


PROVIDER_ERRORS = (
    SetupError,
    GitHubAPIError,
    SlackApiError,
    httpx.HTTPError,
    URLError,
    TimeoutError,
)


def safe_provider_error(error: Exception) -> SetupError:
    if isinstance(error, SetupError):
        return error
    if isinstance(error, SlackApiError) and error.response.get("error") == "missing_scope":
        return SetupError("missing_scopes", "Grant the required Slack scopes and reconnect.")
    return SetupError(
        "provider_unavailable",
        "Check app installation, permissions and network access, then retry or reconnect.",
    )


ERROR_DETAILS = {
    "binding_changed": "The selected repository changed. Relink the issue to verify access.",
    "rate_limited": "GitHub asked us to wait. The status will refresh after that delay.",
    "demo_workspace": DEMO_DETAIL,
    "disconnected": "Reconnect GitHub in workspace settings, then refresh.",
    "issue_transferred": (
        "This issue moved to another repository. Review the link and selected repository."
    ),
    "inaccessible": "GitHub could not grant access to this issue. Check permissions, then refresh.",
    "repository_removed": "Restore this repository in the GitHub App installation, then reconnect.",
    "missing_scopes": "Grant the required app permissions and reconnect.",
    "identity_mismatch": "The connected identity changed. Reconnect to verify it.",
    "repository_changed": (
        "The repository identity changed. Select it again and reauthorise GitHub."
    ),
    "credential_unavailable": "Ask the operator to restore the encryption key, then reconnect.",
    "operator_setup": "Ask the operator to configure the provider application and encryption key.",
    "channel_ineligible": (
        "Check allowed channels: invite the bot and remove archived or externally shared channels."
    ),
    "provider_unavailable": (
        "Check app installation, permissions and network access, then retry or reconnect."
    ),
    "access_lost": (
        "GitHub access was lost: the installation or selected repository was removed. "
        "Reinstall the App on this repository, then reconnect."
    ),
    "app_uninstalled": "The Slack App was removed from this workspace. Reconnect Slack.",
    "credentials_revoked": "Slack revoked the app's access. Reconnect Slack.",
    "github_credentials_invalid": (
        "GitHub rejected the app's credentials. Ask the operator to check the GitHub App "
        "key, then reconnect."
    ),
    "installation_suspended": (
        "The GitHub App installation is suspended. Unsuspend it in GitHub, then refresh."
    ),
    "model_auth_rejected": "The provider rejected the API key. Enter a new key and reconnect.",
    "model_not_found": "The provider does not offer this model. Check the model name.",
    "model_rate_limited": "The provider asked us to slow down. Wait, then check the status.",
    "model_request_rejected": (
        "The provider rejected the request. Check that the model supports JSON schema output."
    ),
    "model_no_structured_output": (
        "The model did not return JSON that matches the schema. "
        "Use a model that supports JSON schema output."
    ),
    "model_refused": "The model refused the request. Try another model.",
    "endpoint_blocked": (
        "The base URL must resolve only to public addresses. "
        "Ask the operator to configure local or private servers."
    ),
    "key_required": "Enter an API key. A changed base URL or API style needs a new key.",
    "deployment_managed": (
        "This deployment sets the model provider. Enable it with consent; the values are fixed."
    ),
    "model_not_connected": "Connect a model provider in workspace settings.",
}
