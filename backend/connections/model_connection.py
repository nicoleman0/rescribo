"""An owner connects the workspace's model provider with a key and consent."""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from accounts.models import Membership
from connections.credentials import cipher, decrypt
from connections.errors import SetupError, known_error
from connections.model_access import deployment, deployment_client
from connections.models import Connection
from connections.services import lock_owner, refuse_demo
from integrations.model.clients import Endpoint, ModelClient
from integrations.model.config import API_STYLES
from integrations.model.endpoint import validate_settings_url
from integrations.model.probe import check_model

CONSENT_DETAIL = (
    "Confirm that conversation and report content from this workspace may be sent to the "
    "model provider."
)


def connect_model(
    actor: Membership, *, api_style: str, base_url: str, model: str, api_key: str, consent: bool
) -> None:
    """Run the connection test, then save. A failed test saves nothing."""
    refuse_demo(actor)
    if not consent:
        raise SetupError("consent_required", CONSENT_DETAIL)
    # Checked again under the lock; this one keeps a non-owner from reaching the provider.
    if not Membership.objects.filter(pk=actor.pk, role="owner", is_active=True).exists():
        raise PermissionDenied()
    stored = Connection.objects.filter(
        workspace_id=actor.workspace_id, provider=Connection.Provider.MODEL
    ).first()
    reused = ""
    config = deployment()
    if config is not None:
        if api_style or base_url or model or api_key:
            raise known_error("deployment_managed")
        client = deployment_client(config)
        values = {"api_style": "", "base_url": "", "model": "", "credential": ""}
    else:
        if api_style not in API_STYLES or not model.strip():
            raise SetupError("invalid_request", "Choose an API style and enter a model name.")
        base_url = validate_settings_url(base_url)
        if not api_key:
            # A stored key may only go back to the endpoint it was entered for.
            if (
                stored is None
                or not stored.credential
                or (stored.api_style, stored.base_url) != (api_style, base_url)
            ):
                raise known_error("key_required")
            reused = stored.credential
            api_key = decrypt(reused)
        client = ModelClient(
            Endpoint(api_style, base_url, model.strip(), private_allowed=False), api_key
        )
        values = {
            "api_style": api_style,
            "base_url": base_url,
            "model": model.strip(),
            "credential": reused,
        }
    # Before any lock: the test can take up to a minute.
    check_model(client)
    if config is None and not reused:
        values["credential"] = cipher().encrypt(api_key.encode()).decode()
    with transaction.atomic():
        lock_owner(actor)
        row, _ = Connection.objects.select_for_update().get_or_create(
            workspace_id=actor.workspace_id, provider=Connection.Provider.MODEL
        )
        if reused and row.credential != reused:
            raise SetupError(
                "version_conflict", "Settings changed. Reload them before trying again."
            )
        for key, value in values.items():
            setattr(row, key, value)
        now = timezone.now()
        row.status = Connection.Status.ACTIVE
        row.error_code = ""
        row.last_success_at = now
        row.consented_at = now
        row.version += 1
        row.save()
