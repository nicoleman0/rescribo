"""Provider boundary for settings use cases."""

from connections.credentials import cipher as cipher
from connections.errors import PROVIDER_ERRORS as PROVIDER_ERRORS
from connections.errors import SetupError as SetupError
from connections.errors import safe_provider_error as safe_provider_error
from connections.model_access import check_model_row
from connections.models import Connection
from integrations.github_app.settings import check_github
from integrations.github_app.settings import github_setup as github_setup
from integrations.slack.settings import channel_details as channel_details
from integrations.slack.settings import channel_options as channel_options
from integrations.slack.settings import check_slack
from integrations.slack.settings import slack_setup as slack_setup


def check_connection(row: Connection) -> None:
    if row.provider == Connection.Provider.SLACK:
        check_slack(row.credential, row.external_id)
    elif row.provider == Connection.Provider.GITHUB:
        check_github(row.external_id, row.repository, row.repository_id)
    else:
        check_model_row(row)
