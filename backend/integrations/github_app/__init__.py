"""GitHub App integration boundary."""

from integrations.github_app.client import GitHubAppClient
from integrations.github_app.probe import InstallationProbe, ProbeResult
from integrations.github_app.state import OAuthStateStore

__all__ = ["GitHubAppClient", "InstallationProbe", "OAuthStateStore", "ProbeResult"]
