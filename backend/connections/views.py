"""Owner settings endpoints and session-bound OAuth callbacks."""

import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import HttpResponseRedirect
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.views import ErrorSerializer, OwnerWorkspaceView, WorkspaceView
from connections import providers, services, slack_identity, slack_inbound, slack_outcomes
from connections.models import Connection
from feedback.deletion import delete_report, delete_workspace
from feedback.errors import VersionConflict
from feedback.models import ReportSource
from integrations.github_app.webhooks import (
    InvalidWebhookPayload,
    InvalidWebhookSignature,
    parse_delivery,
    verify_webhook_signature,
)
from integrations.slack.errors import ChannelRejected
from integrations.slack.messages import outcome_action_pairs
from integrations.slack.shortcuts import ShortcutPayloadError
from integrations.slack.signing import InvalidSlackSignature, verify_slack_signature
from operations.models import InboundReceipt
from operations.tasks import process_inbound_receipt

logger = logging.getLogger(__name__)


class ChannelSerializer(serializers.Serializer):
    channel_id = serializers.CharField()
    name = serializers.CharField()
    is_private = serializers.BooleanField()
    verified_at = serializers.DateTimeField()


class OperationCountsSerializer(serializers.Serializer):
    queued = serializers.IntegerField()
    running = serializers.IntegerField()
    failed = serializers.IntegerField()
    uncertain = serializers.IntegerField()


class ConnectionSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=Connection.Provider.choices)
    identity = serializers.CharField()
    external_id = serializers.CharField()
    status = serializers.ChoiceField(choices=Connection.Status.choices)
    scopes = serializers.ListField(child=serializers.CharField())
    error_code = serializers.CharField()
    error_detail = serializers.CharField()
    last_success_at = serializers.DateTimeField(allow_null=True)
    last_reconciled_at = serializers.DateTimeField(allow_null=True)
    repository = serializers.CharField()
    visibility = serializers.CharField()
    version = serializers.IntegerField()
    channels = ChannelSerializer(many=True)
    operations = OperationCountsSerializer()


class VersionSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)


class DisconnectSerializer(VersionSerializer):
    confirmation = serializers.ChoiceField(choices=["DISCONNECT"])


class SetupSerializer(serializers.Serializer):
    repository = serializers.RegexField(
        r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", required=False, default=""
    )
    consent = serializers.BooleanField()


class URLSerializer(serializers.Serializer):
    url = serializers.URLField()


class ChannelInputSerializer(VersionSerializer):
    channel_id = serializers.RegexField(r"^[CG][A-Z0-9]+$", max_length=64)
    remove = serializers.BooleanField(default=False)
    consent = serializers.BooleanField(default=False)


class DeleteSerializer(serializers.Serializer):
    confirmation = serializers.CharField()


class DeleteReportSerializer(DeleteSerializer):
    version = serializers.IntegerField(min_value=1)


def translated(action: Callable[[], Any]) -> Response:
    try:
        result = action()
        return Response(result, status=200 if result is not None else 204)
    except providers.SetupError as error:
        return Response(
            {"detail": error.detail, "reason": error.code, "field_errors": {}},
            status=409 if error.code == "version_conflict" else 400,
        )
    except VersionConflict:
        return Response(
            {
                "detail": "The report changed. Reload it before deleting.",
                "reason": "version_conflict",
                "field_errors": {},
            },
            status=409,
        )


def provider_name(provider: str) -> str:
    if provider not in Connection.Provider.values:
        raise NotFound()
    return provider


class ConnectionListView(WorkspaceView):
    @extend_schema(responses={200: ConnectionSerializer(many=True)})
    def get(self, request: Request, workspace_id: UUID) -> Response:
        return Response(
            [
                services.connection_payload(row)
                for row in Connection.objects.filter(workspace_id=workspace_id).order_by("provider")
            ]
        )


class SetupView(OwnerWorkspaceView):
    @extend_schema(request=SetupSerializer, responses={200: URLSerializer, 400: ErrorSerializer})
    def post(self, request: Request, workspace_id: UUID, provider: str) -> Response:
        provider_name(provider)
        data = SetupSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        if (
            not data.validated_data["consent"]
            or provider == "github"
            and not data.validated_data["repository"]
        ):
            return Response(
                {
                    "detail": "Confirm workspace publication and choose a repository for GitHub.",
                    "reason": "consent_required",
                    "field_errors": {},
                },
                status=400,
            )
        return translated(
            lambda: {
                "url": services.start_setup(
                    self.membership,
                    provider,
                    request.session.session_key or "",
                    data.validated_data["repository"],
                )
            }
        )


class CallbackView(OwnerWorkspaceView):
    @extend_schema(exclude=True)
    def get(self, request: Request, workspace_id: UUID, provider: str) -> Any:
        provider_name(provider)
        try:
            services.finish_setup(
                self.membership,
                provider,
                request.session.session_key or "",
                str(request.query_params.get("state", "")),
                str(request.query_params.get("code", "")),
            )
        except providers.PROVIDER_ERRORS as error:
            safe = providers.safe_provider_error(error)
            return Response({"detail": safe.detail, "reason": safe.code}, status=400)
        return HttpResponseRedirect("/settings")


class DisconnectView(OwnerWorkspaceView):
    @extend_schema(
        request=DisconnectSerializer,
        responses={204: None, 400: ErrorSerializer, 409: ErrorSerializer},
    )
    def post(self, request: Request, workspace_id: UUID, provider: str) -> Response:
        data = DisconnectSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return translated(
            lambda: services.disconnect(
                self.membership, provider_name(provider), data.validated_data["version"]
            )
        )


class RefreshView(OwnerWorkspaceView):
    @extend_schema(
        request=VersionSerializer, responses={204: None, 400: ErrorSerializer, 409: ErrorSerializer}
    )
    def post(self, request: Request, workspace_id: UUID, provider: str) -> Response:
        data = VersionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return translated(
            lambda: services.refresh_connection(
                self.membership, provider_name(provider), data.validated_data["version"]
            )
        )


class ChannelView(OwnerWorkspaceView):
    @extend_schema(
        request=ChannelInputSerializer,
        responses={204: None, 400: ErrorSerializer, 409: ErrorSerializer},
    )
    def post(self, request: Request, workspace_id: UUID) -> Response:
        data = ChannelInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        if not values.pop("consent") and not values["remove"]:
            return Response(
                {
                    "detail": "Confirm that reports from this channel may be read "
                    "by every workspace member.",
                    "reason": "consent_required",
                    "field_errors": {},
                },
                status=400,
            )

        def change() -> None:
            try:
                services.update_channel(self.membership, **values)
            except providers.SetupError:
                raise
            except (*providers.PROVIDER_ERRORS, ChannelRejected) as error:
                if isinstance(error, ChannelRejected):
                    raise providers.SetupError(
                        "channel_ineligible",
                        "Use an active internal channel, invite the bot, "
                        "and exclude DMs and Slack Connect channels.",
                    ) from error
                raise providers.safe_provider_error(error) from error

        return translated(change)


class ReportDeleteView(OwnerWorkspaceView):
    @extend_schema(
        request=DeleteReportSerializer,
        responses={204: None, 400: ErrorSerializer, 409: ErrorSerializer},
    )
    def post(self, request: Request, workspace_id: UUID, report_id: UUID) -> Response:
        data = DeleteReportSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return translated(lambda: delete_report(self.membership, report_id, **data.validated_data))


class WorkspaceDeleteView(OwnerWorkspaceView):
    @extend_schema(request=DeleteSerializer, responses={204: None, 400: ErrorSerializer})
    def post(self, request: Request, workspace_id: UUID) -> Response:
        data = DeleteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return translated(lambda: delete_workspace(self.membership, **data.validated_data))


class SlackIdentitySerializer(serializers.Serializer):
    linked = serializers.BooleanField()
    team_id = serializers.CharField()
    user_id = serializers.CharField()
    linked_at = serializers.DateTimeField(allow_null=True)


class SlackLinkCodeSerializer(serializers.Serializer):
    code = serializers.CharField()
    expires_at = serializers.DateTimeField()


class SlackIdentityView(WorkspaceView):
    """The current member's own Slack link; nobody links or unlinks another member."""

    @extend_schema(responses={200: SlackIdentitySerializer})
    def get(self, request: Request, workspace_id: UUID) -> Response:
        identity = slack_identity.linked_identity(self.membership)
        return Response(
            {
                "linked": identity is not None,
                "team_id": identity.provider_team_id if identity else "",
                "user_id": identity.provider_user_id if identity else "",
                "linked_at": identity.linked_at if identity else None,
            }
        )


class SlackUnlinkView(WorkspaceView):
    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request, workspace_id: UUID) -> Response:
        slack_identity.unlink(self.membership)
        return Response(status=204)


class SlackLinkCodeView(WorkspaceView):
    @extend_schema(request=None, responses={200: SlackLinkCodeSerializer})
    def post(self, request: Request, workspace_id: UUID) -> Response:
        issued = slack_identity.issue_link_code(self.membership)
        return Response({"code": issued.secret, "expires_at": issued.expires_at})


class GitHubWebhookView(APIView):
    """Shared across every workspace; the payload's installation ID resolves the connection.

    The signature is verified against the raw body before any JSON parsing, and
    the view carries no CSRF exemption of its own: DRF's APIView already skips
    Django's CSRF middleware for unauthenticated views, so nothing extra is added.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    body_limit = 1_000_000

    @staticmethod
    def _dispatch(receipt_id: str) -> None:
        try:
            process_inbound_receipt.delay(receipt_id)
        except Exception:
            logger.warning("GitHub receipt dispatch deferred to the durable dispatcher")

    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        secret = settings.RESCRIBO_GITHUB_WEBHOOK_SECRET
        if not secret:
            # An operator configuration gap, not a bad request: fail closed with 500 so
            # GitHub's delivery retries once the secret is set, rather than giving up.
            return Response(status=500)
        if len(request.body) > self.body_limit:
            return Response(status=413)
        try:
            verify_webhook_signature(
                secret=secret.encode(),
                body=request.body,
                signature_header=request.headers.get("X-Hub-Signature-256"),
            )
        except InvalidWebhookSignature:
            return Response(status=401)
        delivery_id = request.headers.get("X-GitHub-Delivery", "")
        if not delivery_id or len(delivery_id) > 128:
            return Response(status=400)
        try:
            delivery = parse_delivery(request.headers, request.body)
        except InvalidWebhookPayload:
            return Response(status=400)
        if delivery is None:
            return Response(status=204)
        try:
            with transaction.atomic():
                receipt, created = InboundReceipt.objects.get_or_create(
                    provider=InboundReceipt.Provider.GITHUB,
                    delivery_id=delivery_id,
                    defaults=asdict(delivery),
                )
        except DatabaseError:
            logger.warning("GitHub receipt could not be persisted")
            return Response(status=500)
        if created:
            transaction.on_commit(lambda: self._dispatch(str(receipt.pk)))
        return Response(status=202)


class SlackRequestView(APIView):
    """Shared across every workspace; the signed team ID resolves the connection.

    The signature is verified against the raw body before any parsing. As with the
    GitHub webhook, DRF skips CSRF for these unauthenticated views.
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]
    body_limit = 1_000_000

    def verified_body(self, request: Request) -> bytes | Response:
        secret = settings.RESCRIBO_SLACK_SIGNING_SECRET
        if not secret:
            return Response(status=500)
        if len(request.body) > self.body_limit:
            return Response(status=413)
        try:
            verify_slack_signature(
                signing_secret=secret,
                body=request.body,
                timestamp=request.headers.get("X-Slack-Request-Timestamp"),
                signature=request.headers.get("X-Slack-Signature"),
            )
        except InvalidSlackSignature:
            return Response(status=401)
        return request.body


class SlackInteractionsView(SlackRequestView):
    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        body = self.verified_body(request)
        if isinstance(body, Response):
            return body
        try:
            payload = json.loads(parse_qs(body.decode())["payload"][0])
        except KeyError, IndexError, UnicodeDecodeError, json.JSONDecodeError:
            return Response(status=400)
        if not isinstance(payload, dict):
            return Response(status=400)
        try:
            if payload.get("type") == "message_action":
                slack_inbound.start_capture(payload)
            elif payload.get("type") == "view_submission":
                return Response(slack_inbound.submit_capture(payload))
            elif payload.get("type") == "block_actions":
                return self._handle_block_actions(payload)
        except ShortcutPayloadError, ValueError:
            return Response(status=400)
        return Response(status=200)

    def _handle_block_actions(self, payload: dict[str, Any]) -> Response:
        for action_id, value in outcome_action_pairs(payload):
            try:
                body = slack_outcomes.handle_outcome_action(
                    payload=payload, action_id=action_id, value=value
                )
            except slack_outcomes.OutcomeRejected as rejected:
                body = {
                    "response_type": "ephemeral",
                    "replace_original": False,
                    "text": rejected.message,
                }
            return Response(body)
        return Response(status=200)


class SlackEventsView(SlackRequestView):
    @extend_schema(exclude=True)
    def post(self, request: Request) -> Response:
        body = self.verified_body(request)
        if isinstance(body, Response):
            return body
        try:
            payload = json.loads(body)
        except UnicodeDecodeError, json.JSONDecodeError:
            return Response(status=400)
        if not isinstance(payload, dict):
            return Response(status=400)
        try:
            result = slack_inbound.handle_event(payload)
        except DatabaseError:
            logger.warning("Slack event could not be persisted")
            return Response(status=500)
        return Response(result) if result is not None else Response(status=200)


class PermalinkSerializer(serializers.Serializer):
    permalink = serializers.CharField()
    permalink_error = serializers.CharField()


class ReportPermalinkRetryView(WorkspaceView):
    @extend_schema(request=None, responses={200: PermalinkSerializer})
    def post(self, request: Request, workspace_id: UUID, report_id: UUID) -> Response:
        source = ReportSource.objects.filter(
            workspace_id=workspace_id, report_id=report_id, kind=ReportSource.Kind.SLACK
        ).first()
        if source is None:
            raise NotFound()
        slack_inbound.resolve_permalink(source.pk)
        source.refresh_from_db(fields=["permalink", "permalink_error"])
        return Response({"permalink": source.permalink, "permalink_error": source.permalink_error})
