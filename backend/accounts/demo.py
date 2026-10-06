"""The single answer to whether a workspace is the demo, which never reaches real providers."""

from uuid import UUID

from accounts.models import Workspace

DEMO_DETAIL = "Integrations are disabled in the demo workspace. Its data is fictitious."


def is_demo_workspace(workspace_id: UUID) -> bool:
    return Workspace.objects.filter(pk=workspace_id, is_demo=True).exists()
