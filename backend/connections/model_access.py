"""The only way code reaches a workspace's model provider.

Features call `model_client(workspace_id)`. It refuses the demo workspace and any
workspace without an active, consented connection before a request is built.
"""

import os
from typing import Any
from uuid import UUID

from django.conf import settings

from accounts.demo import DEMO_DETAIL, is_demo_workspace
from connections.credentials import decrypt
from connections.errors import SetupError, known_error
from connections.models import Connection
from integrations.model.clients import Endpoint, ModelClient
from integrations.model.config import DeploymentModel
from integrations.model.probe import check_model


def deployment() -> DeploymentModel | None:
    model: DeploymentModel | None = settings.RESCRIBO_MODEL_DEPLOYMENT
    return model


def deployment_client(config: DeploymentModel) -> ModelClient:
    key = os.environ.get(config.api_key_env, "") if config.api_key_env else ""
    if config.api_key_env and not key.strip():
        raise SetupError(
            "operator_setup", "Ask the operator to set the model provider's API key variable."
        )
    endpoint = Endpoint(config.api_style, config.base_url, config.model, private_allowed=True)
    return ModelClient(endpoint, key)


def matches_deployment(row: Connection) -> bool:
    """Consent covers the provider it was given for.

    A row enabled for the deployment default keeps no base URL; one set up in
    Settings always has one. When the config file is added or removed, rows from
    the other mode stop working until an owner connects again.
    """
    return (deployment() is not None) == (row.base_url == "")


def row_client(row: Connection) -> ModelClient:
    if row.consented_at is None or not matches_deployment(row):
        raise known_error("model_not_connected")
    config = deployment()
    if config is not None:
        return deployment_client(config)
    endpoint = Endpoint(row.api_style, row.base_url, row.model, private_allowed=False)
    return ModelClient(endpoint, decrypt(row.credential))


def model_client(workspace_id: UUID) -> ModelClient:
    if is_demo_workspace(workspace_id):
        raise SetupError("demo_workspace", DEMO_DETAIL)
    row = Connection.objects.filter(
        workspace_id=workspace_id, provider=Connection.Provider.MODEL
    ).first()
    if row is None or row.status != Connection.Status.ACTIVE:
        raise known_error("model_not_connected")
    return row_client(row)


def check_model_row(row: Connection) -> None:
    check_model(row_client(row))


def model_fields(row: Connection) -> dict[str, Any]:
    """What members see: the deployment's values when it manages the provider."""
    if not matches_deployment(row):
        return {
            "api_style": "",
            "base_url": "",
            "model": "",
            "status": Connection.Status.DISCONNECTED,
            "error_code": "",
        }
    config = deployment()
    if config is not None:
        return {"api_style": config.api_style, "base_url": config.base_url, "model": config.model}
    return {"api_style": row.api_style, "base_url": row.base_url, "model": row.model}
