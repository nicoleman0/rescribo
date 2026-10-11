"""The single answer to whether a workspace is the demo, which never reaches real providers."""

from uuid import UUID

from django.conf import settings

from accounts.models import Workspace

DEMO_SLUG = "demo"
VISITOR_EMAIL = "demo@example.com"
DEMO_DETAIL = "Integrations are disabled in the demo workspace. Its data is fictitious."


def demo_offer() -> dict[str, str] | None:
    password = settings.RESCRIBO_DEMO_PASSWORD
    if not password or not Workspace.objects.filter(slug=DEMO_SLUG, is_demo=True).exists():
        return None
    return {"email": VISITOR_EMAIL, "password": password}


def is_demo_workspace(workspace_id: UUID) -> bool:
    return Workspace.objects.filter(pk=workspace_id, is_demo=True).exists()
