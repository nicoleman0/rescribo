"""Provider boundary for settings use cases."""

from connections.credentials import cipher as cipher
from connections.errors import PROVIDER_ERRORS as PROVIDER_ERRORS
from connections.errors import SetupError as SetupError
from connections.errors import safe_provider_error as safe_provider_error
from integrations.github_app.settings import check_github
from integrations.github_app.settings import github_setup as github_setup
from integrations.slack.settings import channel_details as channel_details
from integrations.slack.settings import check_slack
from integrations.slack.settings import slack_setup as slack_setup


def check_connection(
    provider: str, credential: str, external_id: str, repository: str, repository_id: str
) -> None:
    if provider == "slack":
        check_slack(credential, external_id)
    else:
        check_github(external_id, repository, repository_id)
